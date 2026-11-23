"""Read-only: stream a session's Drive recordings to the review worker for benchmarking.

Run inside the production Odoo container with `odoo shell` (see docs/AI_REVIEW_PROVIDER_HANDOFF.md):

    SESSIONS=123,456 WORKER_URL=http://10.77.160.36:8090 WORKER_TOKEN=... \
        odoo shell -c /etc/odoo/odoo.conf -d kimacademy --no-http < push_review_sample.py

- Uses the existing Drive OAuth connection to read files. Writes nothing to Odoo: the transaction is
  rolled back at the end (a refreshed access token is not kept).
- Sends video bytes and the roster only to the worker on the internal network.
- Prints session id, job key, part numbers, sizes and status. Never prints tokens, URLs or names.
- Re-running with the same session resumes upload at the worker's received offset (same job key).
"""
import hashlib
import os

import requests

from odoo.addons.edu_video.models.job import parse_drive_url

CHUNK = 32 * 1024 * 1024
WORKER = os.environ['WORKER_URL'].rstrip('/')
HEADERS = {'Authorization': 'Bearer ' + os.environ['WORKER_TOKEN']}
SESSIONS = [int(x) for x in os.environ['SESSIONS'].split(',') if x.strip()]

config = env.ref('edu_video.config_default').sudo()  # noqa: F821 - provided by odoo shell
TOKEN = {'value': None, 'expires': 0}


def drive_token(force=False):
    """Never write edu.video.config: a write would row-lock it for this whole long transaction
    and stall the production video/AI workers. Use the cached token or refresh in memory only."""
    import time
    if not force and TOKEN['value'] and TOKEN['expires'] > time.time() + 120:
        return TOKEN['value']
    if not force and config.access_token and config.expires_at > time.time() + 600:
        TOKEN.update(value=config.access_token, expires=config.expires_at)
        return TOKEN['value']
    r = requests.post('https://oauth2.googleapis.com/token', timeout=30, data={
        'client_id': config.client_id, 'client_secret': config.client_secret,
        'refresh_token': config.refresh_token, 'grant_type': 'refresh_token'})
    if r.status_code != 200:
        raise SystemExit('Drive token refresh HTTP %s' % r.status_code)
    data = r.json()
    TOKEN.update(value=data['access_token'], expires=time.time() + int(data.get('expires_in', 3600)))
    return TOKEN['value']


def drive_get(file_id, resource_key, **kwargs):
    headers = kwargs.pop('headers', {})
    if resource_key:
        headers['X-Goog-Drive-Resource-Keys'] = '%s/%s' % (file_id, resource_key)
    for attempt in range(2):
        headers['Authorization'] = 'Bearer ' + drive_token(force=bool(attempt))
        response = requests.get('https://www.googleapis.com/drive/v3/files/' + file_id, headers=headers,
                                timeout=(10, 120), allow_redirects=False, **kwargs)
        if response.status_code != 401:
            return response
        response.close()
    return response


def job_key(session, parts):
    digest = hashlib.sha256(('bench|%s|%s' % (session.id, session._review_signature())).encode()).hexdigest()
    return 'bench-%s-%s' % (session.id, digest[:16])


env.cr.execute('SET TRANSACTION READ ONLY')  # noqa: F821 - any accidental write fails instead of locking
try:
    for session in env['edu.session'].sudo().browse(SESSIONS):  # noqa: F821
        sources = session._review_sources()
        parts = []
        for source in sources:
            file_id, resource_key = parse_drive_url(source['drive'])
            with drive_get(file_id, resource_key, params={
                    'fields': 'size,mimeType,md5Checksum,capabilities(canDownload)', 'supportsAllDrives': 'true'}) as r:
                if r.status_code != 200:
                    raise SystemExit('session %s part %s: Drive metadata HTTP %s' % (session.id, source['number'], r.status_code))
                info = r.json()
            if not info.get('capabilities', {}).get('canDownload') or not info.get('md5Checksum'):
                raise SystemExit('session %s part %s: not downloadable' % (session.id, source['number']))
            parts.append({'number': source['number'], 'size': int(info['size']), 'md5': info['md5Checksum'],
                          '_file': (file_id, resource_key)})
        spec = {'roster': session._review_roster(), 'prompt_version': '2.1',
                'planned_minutes': max(0, (session.time_end - session.time_start) * 60),
                'parts': [{k: v for k, v in p.items() if not k.startswith('_')} for p in parts]}
        key = job_key(session, parts)
        r = requests.put(WORKER + '/v1/jobs/' + key, json=spec, headers=HEADERS, timeout=30)
        r.raise_for_status()
        job = r.json()
        for part in parts:
            state = job['parts'][str(part['number'])]
            offset = state['received']
            while not state['verified'] and offset < part['size']:
                end = min(offset + CHUNK, part['size']) - 1
                with drive_get(*part['_file'], params={'alt': 'media', 'supportsAllDrives': 'true'},
                               headers={'Range': 'bytes=%s-%s' % (offset, end)}, stream=True) as d:
                    if d.status_code != 206:
                        raise SystemExit('session %s part %s: Drive range HTTP %s' % (session.id, part['number'], d.status_code))
                    data = d.raw.read(end - offset + 2)
                if len(data) != end - offset + 1:
                    raise SystemExit('session %s part %s: short Drive read' % (session.id, part['number']))
                u = requests.put('%s/v1/jobs/%s/parts/%s' % (WORKER, key, part['number']), data=data, timeout=(10, 300),
                                 headers=dict(HEADERS, **{'Content-Range': 'bytes %s-%s/%s' % (offset, end, part['size'])}))
                if u.status_code == 409 and u.json().get('error') == 'offset':
                    offset = u.json()['received']
                    continue
                u.raise_for_status()
                state = u.json()['parts'][str(part['number'])]
                offset = state['received']
                print('session %s part %s: %d/%d MB' % (session.id, part['number'], offset // 2**20, part['size'] // 2**20))
        r = requests.post(WORKER + '/v1/jobs/%s/start' % key, headers=HEADERS, timeout=30)
        r.raise_for_status()
        print('session %s -> job %s state=%s parts=%s' % (session.id, key, r.json()['state'], len(parts)))
finally:
    env.cr.rollback()  # noqa: F821 - read-only: never keep any change
