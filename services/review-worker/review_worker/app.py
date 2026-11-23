"""HTTP API for Odoo. Every call is idempotent and keyed by the job key Odoo checkpoints first.

PUT    /v1/jobs/{key}                 create (same spec -> same job; other spec -> 409)
GET    /v1/jobs/{key}                 state, progress, per-part received bytes, result when done
PUT    /v1/jobs/{key}/parts/{n}       append bytes; header Content-Range: bytes a-b/total, a must equal received
POST   /v1/jobs/{key}/start           queue once all parts are verified (idempotent)
POST   /v1/jobs/{key}/ack             Odoo stored the result: purge files, keep receipt
DELETE /v1/jobs/{key}                 cancel and purge
GET    /healthz                       liveness, no auth
"""
import hashlib
import hmac
import logging
import re
import shutil
import threading
import time
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from . import PIPELINE_VERSION
from .config import load
from .pipeline import Cancelled, Pipeline
from .store import KEY, Conflict, Store

_logger = logging.getLogger('review_worker')
RANGE = re.compile(r'bytes ([0-9]+)-([0-9]+)/([0-9]+)')
MAX_CHUNK = 64 * 1024 ** 2

settings = load()
store = Store(settings.data_dir)
app = FastAPI(title='Kim review worker', docs_url=None, redoc_url=None, openapi_url=None)
upload_lock = threading.Lock()


def auth(authorization: str = Header(default='')):
    expected = 'Bearer ' + settings.token
    if not settings.token or not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(401, 'unauthorized')


def job_or_404(key):
    if not KEY.fullmatch(key):
        raise HTTPException(400, 'key')
    job = store.get(key)
    if not job:
        raise HTTPException(404, 'not_found')
    return job


@app.get('/healthz')
def health():
    return {'ok': True, 'pipeline_version': PIPELINE_VERSION, 'backend': settings.synth_backend}


@app.put('/v1/jobs/{key}', dependencies=[Depends(auth)])
async def create(key: str, request: Request):
    try:
        job = store.create(key, await request.json())
    except Conflict as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return job


@app.get('/v1/jobs/{key}', dependencies=[Depends(auth)])
def status(key: str):
    return job_or_404(key)


@app.put('/v1/jobs/{key}/parts/{number}', dependencies=[Depends(auth)])
async def upload(key: str, number: int, request: Request, content_range: str = Header(default='')):
    job = job_or_404(key)
    if job['state'] != 'receiving':
        raise HTTPException(409, 'not_receiving')
    part = next((p for p in store.spec(key)['parts'] if p['number'] == number), None)
    if not part:
        raise HTTPException(404, 'part')
    if job['parts'][str(number)]['verified']:
        return job  # retried final chunk after a lost response
    match = RANGE.fullmatch(content_range)
    if not match:
        raise HTTPException(400, 'content_range')
    start, end, total = map(int, match.groups())
    if total != part['size'] or end < start or end >= total or end - start + 1 > MAX_CHUNK:
        raise HTTPException(400, 'content_range')
    path = store.part_path(key, number)
    with upload_lock:
        received = path.stat().st_size if path.exists() else 0
        if start != received:
            # Client resumes from GET .../parts[n].received
            return JSONResponse({'error': 'offset', 'received': received}, status_code=409)
        if shutil.disk_usage(path.parent).free < (end - start + 1) + 2 * 1024 ** 3:
            raise HTTPException(507, 'disk')
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > end - start + 1:
                raise HTTPException(400, 'length')
        if len(data) != end - start + 1:
            raise HTTPException(400, 'length')
        with path.open('ab') as output:
            output.write(data)
        if end + 1 == total:
            digest = hashlib.md5()
            with path.open('rb') as source:
                for block in iter(lambda: source.read(8 * 1024 ** 2), b''):
                    digest.update(block)
            if digest.hexdigest() != part['md5']:
                path.unlink(missing_ok=True)
                raise HTTPException(422, 'md5')
            store.mark_verified(key, number)
    return store.get(key)


@app.post('/v1/jobs/{key}/start', dependencies=[Depends(auth)])
def start(key: str):
    job_or_404(key)
    try:
        return store.start(key)
    except Conflict as exc:
        raise HTTPException(409, str(exc))


@app.post('/v1/jobs/{key}/ack', dependencies=[Depends(auth)])
def ack(key: str):
    job_or_404(key)
    job = store.ack(key)
    if not job:
        raise HTTPException(409, 'not_done')
    return job


@app.delete('/v1/jobs/{key}', dependencies=[Depends(auth)])
def cancel(key: str):
    job_or_404(key)
    return store.cancel(key)


# ----------------------------------------------------------------- sequential runner
def in_window(now=None):
    if not settings.run_window:
        return True
    start, end = (datetime.strptime(v, '%H:%M').time() for v in settings.run_window.split('-'))
    now = (now or datetime.now()).time()
    return start <= now < end if start < end else now >= start or now < end


def runner():
    pipeline = Pipeline(store, settings)
    last_expire = 0
    while True:
        try:
            if time.time() - last_expire > 600:
                store.expire(settings.retention_hours)
                last_expire = time.time()
            key = store.claim_next() if in_window() else None
            if not key:
                time.sleep(15)
                continue
            row = store.row(key)
            if row['attempts'] > settings.max_attempts:
                store.update(key, state='failed', error=row['error'] or 'attempts', finished=time.time())
                store.drop_media(key)
                continue
            try:
                pipeline.run(key)
            except Cancelled:
                pass
            except Exception as exc:  # noqa: BLE001 - keep only a short code, never transcript text
                code = str(exc)[:200] if isinstance(exc, RuntimeError) else type(exc).__name__
                _logger.warning('job %s attempt %s failed: %s', key, row['attempts'], code)
                final = row['attempts'] >= settings.max_attempts
                store.update(key, state='failed' if final else 'queued', error=code,
                             finished=time.time() if final else None)
                if final:
                    store.drop_media(key)
                else:
                    time.sleep(60)
        except Exception:  # noqa: BLE001
            _logger.exception('runner loop error')
            time.sleep(30)


@app.on_event('startup')
def boot():
    logging.basicConfig(level=logging.INFO)
    if not settings.token or len(settings.token) < 32:
        raise RuntimeError('WORKER_TOKEN must be set (32+ chars)')
    threading.Thread(target=runner, name='runner', daemon=True).start()
