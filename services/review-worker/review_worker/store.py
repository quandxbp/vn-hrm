"""Durable job state in SQLite. One row per Odoo job key; files under data_dir/jobs/<key>."""
import hashlib
import json
import re
import shutil
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

KEY = re.compile(r'[a-z0-9][a-z0-9-]{7,79}')
STATES = ('receiving', 'queued', 'running', 'done', 'failed', 'cancelled')
MEDIA_GLOBS = ('part-*.video', 'part-*.wav', 'frames-*')


class Conflict(Exception):
    pass


def canonical_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def validate_spec(spec):
    """Validate the job spec sent by Odoo. Raise ValueError with a short code."""
    if not isinstance(spec, dict) or set(spec) - {'roster', 'planned_minutes', 'parts', 'prompt_version'}:
        raise ValueError('spec')
    parts = spec.get('parts')
    if not isinstance(parts, list) or not 1 <= len(parts) <= 10:
        raise ValueError('parts')
    numbers = []
    for part in parts:
        if (not isinstance(part, dict) or type(part.get('number')) is not int or not 1 <= part['number'] <= 99
                or type(part.get('size')) is not int or not 0 < part['size'] <= 2 * 1024 ** 3
                or not re.fullmatch(r'[0-9a-f]{32}', str(part.get('md5', '')))):
            raise ValueError('part')
        numbers.append(part['number'])
    if len(set(numbers)) != len(numbers):
        raise ValueError('part')
    roster = spec.get('roster') or []
    if not isinstance(roster, list) or len(roster) > 60:
        raise ValueError('roster')
    for row in roster:
        if (not isinstance(row, dict) or not re.fullmatch(r'student_[0-9]{1,12}', str(row.get('key', '')))
                or not isinstance(row.get('label'), str) or not isinstance(row.get('aliases', []), list)
                or any(not isinstance(a, str) or len(a) > 200 for a in row.get('aliases', []))):
            raise ValueError('roster')
    planned = spec.get('planned_minutes', 0)
    if isinstance(planned, bool) or not isinstance(planned, (int, float)) or not 0 <= planned <= 600:
        raise ValueError('planned')
    return spec


class Store:
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        (self.root / 'jobs').mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'jobs.sqlite3'
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                key TEXT PRIMARY KEY, spec_hash TEXT NOT NULL, spec TEXT NOT NULL,
                state TEXT NOT NULL, stage TEXT, progress REAL DEFAULT 0, attempts INTEGER DEFAULT 0,
                error TEXT, result TEXT, metrics TEXT, durations TEXT,
                created REAL NOT NULL, updated REAL NOT NULL, finished REAL, acked REAL, purged INTEGER DEFAULT 0)''')
            db.execute('CREATE TABLE IF NOT EXISTS parts (key TEXT, number INTEGER, verified INTEGER DEFAULT 0, '
                       'PRIMARY KEY (key, number))')

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')
        try:
            yield conn
        finally:
            conn.close()

    def job_dir(self, key):
        if not KEY.fullmatch(key or ''):
            raise ValueError('key')
        return self.root / 'jobs' / key

    def part_path(self, key, number):
        return self.job_dir(key) / ('part-%02d.video' % number)

    # ----- job lifecycle -------------------------------------------------
    def create(self, key, spec):
        """Idempotent create. Same key + same spec returns the existing job; else Conflict."""
        validate_spec(spec)
        self.job_dir(key)
        digest = canonical_hash(spec)
        now = time.time()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM jobs WHERE key=?', (key,)).fetchone()
            if row:
                db.execute('COMMIT')
                if row['spec_hash'] != digest:
                    raise Conflict('spec_mismatch')
                return self._public(row)
            db.execute('INSERT INTO jobs (key, spec_hash, spec, state, created, updated) VALUES (?,?,?,?,?,?)',
                       (key, digest, json.dumps(spec, ensure_ascii=False), 'receiving', now, now))
            db.executemany('INSERT INTO parts (key, number) VALUES (?,?)',
                           [(key, p['number']) for p in spec['parts']])
            db.execute('COMMIT')
        self.job_dir(key).mkdir(mode=0o700, exist_ok=True)
        return self.get(key)

    def row(self, key):
        with self.db() as db:
            return db.execute('SELECT * FROM jobs WHERE key=?', (key,)).fetchone()

    def get(self, key):
        row = self.row(key)
        return self._public(row) if row else None

    def spec(self, key):
        return json.loads(self.row(key)['spec'])

    def _public(self, row):
        with self.db() as db:
            parts = {r['number']: bool(r['verified']) for r in
                     db.execute('SELECT number, verified FROM parts WHERE key=?', (row['key'],))}
        spec = json.loads(row['spec'])
        received = {}
        for p in spec['parts']:
            path = self.part_path(row['key'], p['number'])
            received[str(p['number'])] = {'size': p['size'], 'verified': parts.get(p['number'], False),
                                          'received': p['size'] if parts.get(p['number']) else
                                          (path.stat().st_size if path.exists() else 0)}
        return {'key': row['key'], 'state': row['state'], 'stage': row['stage'], 'progress': row['progress'],
                'attempts': row['attempts'], 'error': row['error'],
                'durations': json.loads(row['durations']) if row['durations'] else None,
                'result': json.loads(row['result']) if row['result'] else None,
                'metrics': json.loads(row['metrics']) if row['metrics'] else None,
                'parts': received, 'created': row['created'], 'finished': row['finished'],
                'acked': row['acked'], 'purged': bool(row['purged'])}

    def update(self, key, **values):
        values['updated'] = time.time()
        for name in ('result', 'metrics', 'durations'):
            if name in values and values[name] is not None and not isinstance(values[name], str):
                values[name] = json.dumps(values[name], ensure_ascii=False)
        cols = ', '.join('%s=?' % k for k in values)
        with self.db() as db:
            db.execute('UPDATE jobs SET %s WHERE key=?' % cols, (*values.values(), key))

    def mark_verified(self, key, number, verified=True):
        with self.db() as db:
            db.execute('UPDATE parts SET verified=? WHERE key=? AND number=?', (int(verified), key, number))

    def start(self, key):
        """Idempotent: queue only once every part is verified. Never re-queues done/failed."""
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state FROM jobs WHERE key=?', (key,)).fetchone()
            if not row:
                db.execute('COMMIT')
                return None
            if row['state'] == 'receiving':
                missing = db.execute('SELECT COUNT(*) FROM parts WHERE key=? AND verified=0', (key,)).fetchone()[0]
                if missing:
                    db.execute('COMMIT')
                    raise Conflict('parts_incomplete')
                db.execute("UPDATE jobs SET state='queued', updated=? WHERE key=?", (time.time(), key))
            db.execute('COMMIT')
        return self.get(key)

    def claim_next(self):
        """Pick one job for the single sequential runner. Running jobs are resumed after a crash."""
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT key FROM jobs WHERE state IN ('running', 'queued') "
                             "ORDER BY CASE state WHEN 'running' THEN 0 ELSE 1 END, created LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE jobs SET state='running', attempts=attempts+1, updated=? WHERE key=?",
                           (time.time(), row['key']))
            db.execute('COMMIT')
        return row['key'] if row else None

    def ack(self, key):
        row = self.row(key)
        if not row or row['state'] != 'done':
            return None
        self.update(key, acked=time.time())
        self.purge(key, keep_result=True)
        return self.get(key)

    def cancel(self, key):
        row = self.row(key)
        if not row:
            return None
        if row['state'] not in ('done', 'failed'):
            self.update(key, state='cancelled', finished=time.time())
        self.purge(key, keep_result=row['state'] == 'done')
        return self.get(key)

    # ----- retention -----------------------------------------------------
    def drop_media(self, key):
        folder = self.job_dir(key)
        for pattern in MEDIA_GLOBS:
            for item in folder.glob(pattern):
                shutil.rmtree(item) if item.is_dir() else item.unlink(missing_ok=True)

    def purge(self, key, keep_result=False):
        """Delete all job files (media, transcript, intermediates). The row stays as an idempotency
        receipt; the result JSON is kept only until the retention deadline."""
        shutil.rmtree(self.job_dir(key), ignore_errors=True)
        values = {'purged': 1}
        if not keep_result:
            values['result'] = None
        self.update(key, **values)

    def expire(self, retention_hours):
        deadline = time.time() - retention_hours * 3600
        with self.db() as db:
            rows = db.execute('SELECT key, state FROM jobs WHERE created < ? AND (purged=0 OR result IS NOT NULL)',
                              (deadline,)).fetchall()
        for row in rows:
            if row['state'] in ('receiving', 'queued', 'running'):
                self.update(row['key'], state='failed', error='expired', finished=time.time())
            self.purge(row['key'], keep_result=False)
        return len(rows)
