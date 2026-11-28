"""Internal review worker runs, in two modes.

shadow:   next to a finished Gemini report, for comparison. Never writes to edu.session.review.
official: for a taught session WITHOUT any finished report (no review, or only failed ones;
          approved 23/11/2026). On success it creates ONE new edu.session.review in state done
          (model_name kim-worker/...), exactly like a Gemini result, so the session, duration
          warning, billing suggestion and teacher page use it. Old failed reports are untouched
          (analysis_started is never reset). Published only if, at that moment, the session still
          has no done report, no Gemini run in progress, the same Drive/roster/schedule and an
          unlocked week; otherwise the result stays on this row only.

Never writes to the session, attendance, payroll or week locks. Disabled until the cron is
turned on and the system parameters below are set. Rows are processed strictly one at a time
on the worker: the next upload starts only when no other row is waiting on the worker.

  edu_review_shadow.worker_url     http://10.77.160.36:8090 (internal network only)
  edu_review_shadow.worker_token   bearer token from E:\\KimReview\\app\\.env.worker
  edu_review_shadow.enabled_since  'YYYY-MM-DD HH:MM:SS' UTC; only Gemini reports finished after it
  edu_review_shadow.daily_limit    new shadow jobs per day (default 20)
  edu_review_shadow.prefer_worker_since  'YYYY-MM-DD HH:MM:SS' UTC; empty = off. When set, the worker is the
                                   primary provider (approved 23/11/2026): Gemini auto-queue stops, every
                                   taught session without a finished report is queued here, auto-queued Gemini
                                   requests created before this moment that never reached inference are
                                   cancelled when their session moves here, and a failed worker run falls back
                                   to ONE new Gemini request (never after a Gemini attempt with lost response).
                                   Exception (approved 25/11/2026): a run that failed only because the worker's
                                   Gemini text quota was exhausted (429) never falls back; it is queued again on
                                   the worker under a new job key, and an unsent fallback Gemini request it had
                                   created is cancelled under the Gemini lock.

Duplicate protection: the job key is derived from the report id, Drive signature, roster and
prompt version. Every worker call is idempotent for that key, so a lost response is resolved by
asking the worker for the job state (PUT returns the existing job, uploads resume at the
worker's received offset, start of a running/done job is a no-op). Nothing is resent blindly.
"""
import hashlib
import json
import logging
import time
from datetime import timedelta

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.edu_session_review.models.report import validate_report

from .highlight import split_highlights
from odoo.addons.edu_video.models.job import parse_drive_url

_logger = logging.getLogger(__name__)
LOCK = 87426            # edu_session_review uses 87425
CHUNK = 32 * 1024 ** 2
STEP_SECONDS = 240      # upload budget shared by all records in one cron run; the cron runs every 5 minutes
PARAM = 'edu_review_shadow.'
GEMINI_LOCK = 87425     # edu_session_review sequential lock (held by its cron for a whole run)
ACTIVE = ('queued', 'processing', 'analyzing')
FALLBACK_REASONS = ('not_published:parts_mismatch', 'not_published:create_')
# Worker failures caused by the Gemini text quota only (nothing was generated): rerun on the worker.
QUOTA_ERRORS = ('gemini_http_429', 'gemini_quota')


def quota_failure(row):
    return row.state == 'failed' and (row.error or '').startswith('worker:') and any(
        code in row.error for code in QUOTA_ERRORS)


def gemini_touched(review):
    """True once a Gemini request may have reached the provider's inference (or holds a receipt)."""
    return bool(review.analysis_started or review.batch_name or review.batch_token
                or review.provider_response or review.result_json)


class ShadowError(Exception):
    def __init__(self, code, retry=True):
        super().__init__(code)
        self.code, self.retry = code, retry


class ReviewShadow(models.Model):
    _name = 'edu.session.review.shadow'
    _description = 'Nhận xét AI song song (worker nội bộ)'
    _order = 'id desc'
    _rec_name = 'job_key'

    mode = fields.Selection([('shadow', 'So sánh với Gemini'), ('official', 'Báo cáo chính thức'),
                             ('highlight', 'Tìm đoạn nổi bật')], 'Chế độ',
                            default='shadow', required=True, index=True, readonly=True)
    target_review_id = fields.Many2one('edu.session.review', 'Nhận xét nhận đoạn nổi bật', readonly=True, copy=False,
                                       ondelete='set null', index=True)
    review_id = fields.Many2one('edu.session.review', 'Báo cáo Gemini', ondelete='cascade',
                                index=True, readonly=True)
    session_id = fields.Many2one('edu.session', 'Buổi học', required=True, ondelete='cascade', index=True,
                                 readonly=True)
    source_signature = fields.Char(readonly=True, copy=False)
    planned_minutes = fields.Float(readonly=True)
    official_review_id = fields.Many2one('edu.session.review', 'Báo cáo AI đã tạo', readonly=True, copy=False,
                                         ondelete='set null')
    priority = fields.Boolean('Ưu tiên', readonly=True, copy=False, help='Quản lý bấm Phân tích: chạy trước hàng đợi.')
    fallback_checked = fields.Boolean(readonly=True, copy=False)
    fallback_review_id = fields.Many2one('edu.session.review', 'Báo cáo Gemini dự phòng', readonly=True, copy=False,
                                         ondelete='set null')
    fallback_note = fields.Char('Dự phòng Gemini', readonly=True, copy=False)
    job_key = fields.Char('Mã tác vụ worker', required=True, readonly=True, copy=False)
    state = fields.Selection([('upload', 'Đang gửi video'), ('waiting', 'Worker đang xử lý'),
                              ('done', 'Có kết quả'), ('failed', 'Lỗi'), ('skipped', 'Bỏ qua')],
                             'Trạng thái', default='upload', required=True, index=True, readonly=True)
    parts_json = fields.Json(readonly=True, copy=False)       # number/size/md5/file id; no tokens
    roster_json = fields.Json(readonly=True, copy=False)
    uploaded_mb = fields.Integer('Đã gửi (MB)', readonly=True)
    total_mb = fields.Integer('Tổng (MB)', readonly=True)
    worker_stage = fields.Char('Bước worker', readonly=True)
    worker_progress = fields.Float('Tiến độ worker', readonly=True, digits=(3, 2))
    worker_attempts = fields.Integer('Số lần worker chạy', readonly=True)
    error = fields.Char('Lỗi', readonly=True)
    failures = fields.Integer(readonly=True)
    next_check = fields.Datetime(readonly=True)
    finished_at = fields.Datetime('Xong lúc', readonly=True)
    acked = fields.Boolean('Đã báo worker xóa dữ liệu', readonly=True)
    result_json = fields.Json(readonly=True, copy=False)
    durations_json = fields.Json(readonly=True, copy=False)
    metrics_json = fields.Json(readonly=True, copy=False)
    wall_minutes = fields.Float('Thời gian xử lý (phút)', readonly=True, digits=(8, 1))
    peak_rss_mb = fields.Integer('RAM đỉnh (MB)', readonly=True)

    w_score_available = fields.Boolean('Worker có điểm', readonly=True)
    w_score_total = fields.Float('Điểm worker / 10', readonly=True, digits=(4, 1))
    w_teaching_minutes = fields.Float('Dạy thực tế worker (phút)', readonly=True, digits=(12, 2))
    w_total_minutes = fields.Float('Tổng video worker (phút)', readonly=True, digits=(12, 2))
    w_teaching_started_at = fields.Char('Bắt đầu dạy (worker)', readonly=True)
    w_interaction_level = fields.Char('Tương tác (worker)', readonly=True)
    w_summary = fields.Text('Tổng quát (worker)', readonly=True)
    w_lesson_content = fields.Text('Nội dung đã dạy (worker)', readonly=True)
    w_strengths = fields.Text('Điểm mạnh (worker)', readonly=True)
    w_improvements = fields.Text('Cần cải thiện (worker)', readonly=True)
    w_timing_note = fields.Text('Căn cứ thời gian (worker)', readonly=True)
    w_timing_details = fields.Text('Các khoảng dạy (worker)', readonly=True)
    w_student_report = fields.Text('Học sinh (worker)', readonly=True)
    w_student_alert_count = fields.Integer('Cảnh báo học sinh (worker)', readonly=True)
    w_score_details = fields.Text('Căn cứ chấm điểm (worker)', readonly=True)

    g_score_total = fields.Float(related='review_id.score_total', string='Điểm Gemini / 10')
    g_teaching_minutes = fields.Float(related='review_id.teaching_minutes', string='Dạy thực tế Gemini (phút)')
    g_teaching_started_at = fields.Char(related='review_id.teaching_started_at', string='Bắt đầu dạy (Gemini)')
    g_interaction_level = fields.Selection(related='review_id.interaction_level', string='Tương tác (Gemini)')
    score_diff = fields.Float('Lệch điểm (worker − Gemini)', compute='_compute_diff', store=True, digits=(4, 1))
    teaching_diff = fields.Float('Lệch phút dạy (worker − Gemini)', compute='_compute_diff', store=True,
                                 digits=(8, 1))

    _sql_constraints = [('job_key_unique', 'unique(job_key)', 'Mỗi tác vụ worker chỉ có một bản ghi.'),
                        ('review_unique', 'unique(review_id)', 'Mỗi báo cáo Gemini chỉ chạy song song một lần.')]

    @api.depends('state', 'w_score_total', 'w_teaching_minutes', 'review_id.score_total', 'review_id.teaching_minutes')
    def _compute_diff(self):
        for row in self:
            done = row.state == 'done'
            both = done and row.w_score_available and row.review_id.score_available
            row.score_diff = row.w_score_total - row.review_id.score_total if both else 0
            row.teaching_diff = row.w_teaching_minutes - row.review_id.teaching_minutes if done else 0

    # ------------------------------------------------------------------ configuration
    def _param(self, name, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(PARAM + name, default) or default

    def _ready(self):
        url, token = self._param('worker_url').rstrip('/'), self._param('worker_token')
        if not url.startswith('http') or not token:
            raise UserError('Chưa cấu hình edu_review_shadow.worker_url / worker_token.')
        return url, token

    @staticmethod
    def make_key(review, roster):
        payload = json.dumps([review.id, review.source_signature, roster, review.prompt_version],
                             ensure_ascii=True, sort_keys=True)
        return 'kim-%s-%s' % (review.session_id.id, hashlib.sha256(('shadow|' + payload).encode()).hexdigest()[:16])

    @staticmethod
    def make_official_key(session, signature, roster, planned, rerun=0):
        """`rerun` > 0 only for a new worker run after a quota failure (the first key stays unchanged)."""
        data = [session.id, signature, roster, round(planned, 3), '2.1'] + ([rerun] if rerun else [])
        payload = json.dumps(data, ensure_ascii=True, sort_keys=True)
        return 'kim-%s-%s' % (session.id, hashlib.sha256(('official|' + payload).encode()).hexdigest()[:16])

    @staticmethod
    def _planned(session):
        return max(0, (session.time_end - session.time_start) * 60)

    # ------------------------------------------------------------------ transport (patched in tests)
    def _worker(self, method, path, **kwargs):
        url, token = self._ready()
        headers = dict(kwargs.pop('headers', {}), Authorization='Bearer ' + token)
        try:
            response = requests.request(method, url + path, headers=headers, allow_redirects=False,
                                        timeout=kwargs.pop('timeout', (10, 60)), **kwargs)
        except requests.RequestException as exc:
            raise ShadowError('worker_transport:%s' % type(exc).__name__) from exc
        return response

    def _drive(self, file_id, resource_key, **kwargs):
        config = self.env.ref('edu_video.config_default').sudo()
        headers = dict(kwargs.pop('headers', {}))
        if resource_key:
            headers['X-Goog-Drive-Resource-Keys'] = '%s/%s' % (file_id, resource_key)
        for attempt in range(2):
            headers['Authorization'] = 'Bearer ' + config._token('drive', force=bool(attempt))
            try:
                response = requests.get('https://www.googleapis.com/drive/v3/files/' + file_id, headers=headers,
                                        timeout=(10, 120), allow_redirects=False, **kwargs)
            except requests.RequestException as exc:
                raise ShadowError('drive_transport:%s' % type(exc).__name__) from exc
            if response.status_code != 401:
                return response
            response.close()
        raise ShadowError('drive_auth')

    # ------------------------------------------------------------------ queueing
    @api.model
    def _enqueue(self):
        since = self._param('enabled_since')
        if not since:
            return self.browse()
        limit = int(self._param('daily_limit', '20'))
        today = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        room = limit - self.search_count([('mode', '=', 'shadow'), ('create_date', '>=', today)])
        if room <= 0:
            return self.browse()
        done = self.search([('mode', '=', 'shadow')]).review_id.ids
        reviews = self.env['edu.session.review'].sudo().search(
            [('state', '=', 'done'), ('finished_at', '>=', since), ('id', 'not in', done),
             ('model_name', 'not like', 'kim-worker/%')],  # never compare the worker with itself
            order='finished_at', limit=room * 3)
        created = self.browse()
        for review in reviews:
            if len(created) >= room:
                break
            if not review.source_current or review.session_id.state == 'cancel':
                continue
            roster = review.roster_snapshot or review.session_id._review_roster()
            created |= self.create({'review_id': review.id, 'session_id': review.session_id.id,
                                    'job_key': self.make_key(review, roster), 'roster_json': roster,
                                    'source_signature': review.source_signature,
                                    'planned_minutes': review.planned_minutes})
        return created

    @api.model
    def _prefer_since(self):
        value = self._param('prefer_worker_since')
        try:
            return fields.Datetime.to_datetime(value) if value else False
        except ValueError:
            return False

    @api.model
    def _gemini_split(self, sessions):
        """Active Gemini requests of `sessions` -> (sessions Gemini is busy with, requests the worker may take over).
        Only auto-queued requests from before prefer_worker_since that never reached inference and are not a
        manager's 'Phân tích ngay' can be taken over; everything else keeps the session on Gemini."""
        since = self._prefer_since()
        active = self.env['edu.session.review'].sudo().search([('session_id', 'in', sessions.ids),
                                                               ('state', 'in', list(ACTIVE))])
        movable = active.filtered(lambda r: since and r.create_date < since and not gemini_touched(r)
                                  and not r.immediate_until)
        busy = (active - movable).session_id
        return busy, movable - movable.filtered(lambda r: r.session_id in busy)

    @api.model
    def _official_candidates(self):
        """Taught sessions with Drive video and no finished report, oldest first."""
        sessions = self.env['edu.session'].sudo().search([('state', '=', 'done'), ('ai_review_done', '=', False)],
                                                         order='date, time_start, id')
        busy = self._gemini_split(sessions)[0]
        return sessions.filtered(lambda s: s not in busy and s._review_sources()
                                 and not (s.week_id and s.week_id.is_locked))

    @api.model
    def _official_key(self, session):
        return self.make_official_key(session, session._review_signature(), session._review_roster(),
                                      self._planned(session))

    @api.model
    def _queue_official(self, sessions=None, priority=False):
        """Create one official row per session (idempotent by job key). Returns the new rows.
        Takes over (cancels) movable Gemini requests of a queued session under the Gemini lock, so the
        Gemini cron can never be inside one of them at that moment; without the lock those sessions wait."""
        created = self.browse()
        sessions = sessions if sessions is not None else self._official_candidates()
        busy, movable = self._gemini_split(sessions)
        locked = False
        if movable:
            self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', [GEMINI_LOCK, 0])
            locked = self.env.cr.fetchone()[0]
            if locked:   # re-read under the lock: the Gemini cron may have moved them on
                movable.invalidate_recordset()
                busy, movable = self._gemini_split(sessions)
        for session in sessions:
            sources = session._review_sources()
            if session.state != 'done' or session.ai_review_done or not sources or len(sources) > 10 or session in busy:
                continue
            take = movable.filtered(lambda r: r.session_id == session)
            if take and not locked:
                continue
            roster, planned, signature = session._review_roster(), self._planned(session), session._review_signature()
            key = self.make_official_key(session, signature, roster, planned)
            if self.search_count([('job_key', '=', key)]):
                continue
            take.write({'state': 'cancelled', 'cleanup_pending': True,
                        'error': 'Đã chuyển sang Kim Worker (worker nội bộ được ưu tiên).'})
            created |= self.create({'mode': 'official', 'session_id': session.id, 'job_key': key, 'priority': priority,
                                    'roster_json': roster, 'source_signature': signature, 'planned_minutes': planned})
        return created

    @api.model
    def _requeue_quota_failures(self, rows=None):
        """Official runs that failed only on the worker's Gemini text quota get a new worker run
        (new job key: the worker never reruns a failed job). An unsent fallback Gemini request created
        for such a row is cancelled first, under the Gemini lock; a session Gemini is otherwise busy
        with (sent/started request, 'Phân tích ngay', another open request) is left alone."""
        if rows is None:
            rows = self.search([('mode', '=', 'official'), ('state', '=', 'failed'), '|',
                                ('error', 'like', QUOTA_ERRORS[0]), ('error', 'like', QUOTA_ERRORS[1])], order='id')
        rows = rows.filtered(lambda r: r.mode == 'official').filtered(lambda r: quota_failure(r) and not self.search_count(
            [('session_id', '=', r.session_id.id), ('mode', '=', 'official'), ('id', '>', r.id)]))
        if not rows:
            return self.browse()
        fallbacks = rows.fallback_review_id.filtered(
            lambda r: r.state in ACTIVE and not gemini_touched(r) and not r.immediate_until)
        locked = False
        if fallbacks:
            self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', [GEMINI_LOCK, 0])
            locked = self.env.cr.fetchone()[0]
            if locked:
                fallbacks.invalidate_recordset()
                fallbacks = fallbacks.filtered(lambda r: r.state in ACTIVE and not gemini_touched(r))
        created = self.browse()
        for row in rows:
            session = row.session_id.sudo()
            take = fallbacks.filtered(lambda r: r.session_id == session)
            if take and not locked:
                continue
            sources = session._review_sources()
            other = session.ai_review_ids.filtered(lambda r: r.state in ACTIVE) - take
            if (session.state != 'done' or session.ai_review_done or not sources or len(sources) > 10 or other
                    or (session.week_id and session.week_id.is_locked)):
                continue
            roster, planned, signature = session._review_roster(), self._planned(session), session._review_signature()
            runs = self.search_count([('session_id', '=', session.id), ('mode', '=', 'official')])
            key = self.make_official_key(session, signature, roster, planned, rerun=runs)
            if self.search_count([('job_key', '=', key)]):
                continue
            take.write({'state': 'cancelled', 'cleanup_pending': True,
                        'error': 'Đã chuyển lại sang Kim Worker (worker tạm hết hạn mức Gemini, đã xử lý).'})
            created |= self.create({'mode': 'official', 'session_id': session.id, 'job_key': key,
                                    'priority': row.priority, 'roster_json': roster, 'source_signature': signature,
                                    'planned_minutes': planned})
            row.write({'fallback_checked': True,
                       'fallback_note': ('requeued' + (':gemini_cancelled' if take else ''))})
        return created

    # ------------------------------------------------------------------ steps
    def _spec(self):
        return {'roster': self.roster_json or [], 'prompt_version': '2.1',
                'planned_minutes': self.planned_minutes or 0,
                'parts': [{k: p[k] for k in ('number', 'size', 'md5')} for p in self.parts_json]}

    def _metadata(self):
        parts = []
        for source in self.session_id._review_sources():
            file_id, resource_key = parse_drive_url(source['drive'])
            with self._drive(file_id, resource_key, params={
                    'fields': 'size,mimeType,md5Checksum,capabilities(canDownload)', 'supportsAllDrives': 'true'}) as r:
                if r.status_code != 200:
                    raise ShadowError('drive_metadata_http_%s' % r.status_code, retry=r.status_code >= 500)
                info = r.json()
            if not info.get('capabilities', {}).get('canDownload') or not info.get('md5Checksum'):
                raise ShadowError('drive_not_downloadable', retry=False)
            parts.append({'number': source['number'], 'size': int(info['size']), 'md5': info['md5Checksum'],
                          'file_id': file_id, 'resource_key': resource_key or ''})
        if not parts or len(parts) > 10:
            raise ShadowError('parts_count', retry=False)
        self.write({'parts_json': parts, 'total_mb': sum(p['size'] for p in parts) // 2 ** 20})

    def _job(self, response):
        if response.status_code == 404:
            raise ShadowError('worker_job_missing', retry=False)
        if response.status_code == 409:
            body = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            raise ShadowError('worker_conflict:%s' % str(body.get('error') or body.get('detail') or '')[:40], retry=False)
        if response.status_code != 200:
            raise ShadowError('worker_http_%s' % response.status_code)
        return response.json()

    def _upload(self, deadline):
        if self.source_signature != self.session_id._review_signature():
            self.write({'state': 'skipped', 'error': 'drive_changed'})
            return
        if not self.parts_json:
            self._metadata()
        job = self._job(self._worker('PUT', '/v1/jobs/' + self.job_key, json=self._spec()))
        sent = 0
        for part in self.parts_json:
            state = job['parts'][str(part['number'])]
            offset = state['received']
            while not state['verified'] and offset < part['size']:
                if time.monotonic() > deadline:
                    self.uploaded_mb = (sent + offset) // 2 ** 20
                    return
                end = min(offset + CHUNK, part['size']) - 1
                with self._drive(part['file_id'], part['resource_key'], stream=True,
                                 params={'alt': 'media', 'supportsAllDrives': 'true'},
                                 headers={'Range': 'bytes=%s-%s' % (offset, end)}) as d:
                    if d.status_code != 206 or d.headers.get('Content-Range') != 'bytes %s-%s/%s' % (offset, end, part['size']):
                        raise ShadowError('drive_range_http_%s' % d.status_code)
                    data = d.raw.read(end - offset + 2)
                if len(data) != end - offset + 1:
                    raise ShadowError('drive_short_read')
                u = self._worker('PUT', '/v1/jobs/%s/parts/%s' % (self.job_key, part['number']), data=data,
                                 timeout=(10, 300), headers={'Content-Range': 'bytes %s-%s/%s' % (offset, end, part['size'])})
                if u.status_code == 409 and u.json().get('error') == 'offset':
                    offset = int(u.json()['received'])   # lost response or parallel run: resume where the worker is
                    continue
                if u.status_code == 422:
                    raise ShadowError('worker_md5_mismatch')  # worker discarded the part; next run starts it over
                state = self._job(u)['parts'][str(part['number'])]
                offset = state['received']
            sent += part['size']
        self.uploaded_mb = sent // 2 ** 20
        job = self._job(self._worker('POST', '/v1/jobs/%s/start' % self.job_key))
        self.write({'state': 'waiting', 'worker_stage': job.get('stage') or job.get('state')})

    def _poll(self):
        job = self._job(self._worker('GET', '/v1/jobs/' + self.job_key))
        values = {'worker_stage': job.get('stage') or job.get('state'), 'worker_progress': job.get('progress') or 0,
                  'worker_attempts': job.get('attempts') or 0}
        if job['state'] == 'failed':
            values.update(state='failed', error=('worker:%s' % (job.get('error') or ''))[:120])
        elif job['state'] in ('cancelled', 'expired'):
            values.update(state='failed', error='worker_%s' % job['state'])
        elif job['state'] == 'done':
            values.update(self._result_values(job))
        self.write(values)
        if job['state'] == 'done':
            self._finish()

    def _finish(self):
        """Publish (official mode) BEFORE ack, so a deferred publish is retried while the row is unacked."""
        if self.mode == 'official' and self.state == 'done' and not self.official_review_id \
                and not (self.error or '').startswith('not_published') and not self._publish():
            return
        if self.mode == 'highlight' and self.state == 'done' and not self.fallback_checked:
            self._attach_highlights()
        self._ack()

    def _attach_highlights(self):
        """Only the clips go to the target report, and only while it still describes these videos."""
        review = self.target_review_id.sudo()
        durations = {int(k): float(v) for k, v in (self.durations_json or {}).items()}
        values = split_highlights(self.result_json or {}, durations)[1]
        if not review or review.state != 'done' or review.source_signature != self.source_signature \
                or review.session_id._review_signature() != self.source_signature:
            note = 'not_attached:review_changed'
        elif not values.get('highlight_count'):
            note = 'none'
        else:
            review.write(values)
            note = 'attached:%s' % values['highlight_count']
        self.write({'fallback_checked': True, 'fallback_note': note})

    def _publish(self):
        """Create the official report once. Returns False when it must be retried later.
        Any doubt keeps the result on this row only (error not_published:<reason>)."""
        session = self.session_id
        Review = self.env['edu.session.review'].sudo()
        # The Gemini cron holds (87425, 0) for its whole sequential run: never publish in the middle of it.
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', [GEMINI_LOCK, 0])
        if not self.env.cr.fetchone()[0]:
            self.next_check = fields.Datetime.now() + timedelta(minutes=5)
            return False
        session.invalidate_recordset()
        if session.state == 'done' and not session.ai_review_done and Review.search_count(
                [('session_id', '=', session.id), ('state', 'in', list(ACTIVE))]):
            # A Gemini run (manual/started) is still open: wait for it instead of discarding this result.
            # If it finishes done -> already_reviewed; if it fails -> this result is published.
            self.write({'error': 'publish_wait:gemini_in_progress',
                        'next_check': fields.Datetime.now() + timedelta(minutes=15)})
            return False
        reason = ('session_not_done' if session.state != 'done' else
                  'already_reviewed' if session.ai_review_done else
                  'drive_changed' if session._review_signature() != self.source_signature else
                  'roster_changed' if session._review_roster() != (self.roster_json or []) else
                  'schedule_changed' if abs(self._planned(session) - self.planned_minutes) > 0.001 else False)
        if not reason:
            try:
                with self.env.cr.savepoint():
                    session._check_week_unlocked()
            except UserError:
                reason = 'week_locked'
        if reason:
            self.error = 'not_published:%s' % reason
            return True
        data = self.result_json
        durations = {int(k): float(v) for k, v in (self.durations_json or {}).items()}
        report, clips = split_highlights(data, durations)
        values = validate_report(report, durations, require_v2=True, require_students=bool(self.roster_json),
                                 roster=self.roster_json, planned_minutes=self.planned_minutes)
        values.update(clips)
        model = 'kim-worker/%s' % (((self.metrics_json or {}).get('llm_usage') or {}).get('reduce_model')
                                   or (self.metrics_json or {}).get('reduce_backend') or 'local')
        parts = [fields.Command.create({'number': p['number'], 'source_url': source['drive'], 'file_id': p['file_id'],
                                        'resource_key': p['resource_key'] or False, 'state': 'ready',
                                        'total_bytes': p['size'], 'duration': durations.get(p['number'], 0)})
                 for p in self.parts_json
                 for source in session._review_sources() if source['number'] == p['number']]
        if len(parts) != len(self.parts_json):
            self.error = 'not_published:parts_mismatch'
            return True
        try:
            with self.env.cr.savepoint():
                review = Review.create(dict(
                    values, name='Nhận xét AI — %s' % session.display_name, session_id=session.id,
                    source_signature=self.source_signature, model_name=model[:100],
                    execution_mode='sync', source_policy='drive_only', prompt_version='2.1',
                    roster_snapshot=self.roster_json or [], planned_minutes=self.planned_minutes,
                    part_ids=parts, state='done', result_json=data, requested_by=self.env.ref('base.user_root').id,
                    finished_at=fields.Datetime.now(), cleanup_pending=False))
        except Exception as exc:  # noqa: BLE001 - keep the worker result; a manager decides
            _logger.warning('review worker row %s publish failed: %s', self.id, type(exc).__name__)
            self.error = 'not_published:create_%s' % type(exc).__name__
            return True
        self.write({'official_review_id': review.id, 'error': False})
        return True

    def _result_values(self, job):
        data = job.get('result') or {}
        durations = {int(k): float(v) for k, v in (job.get('durations') or {}).items()}
        metrics = job.get('metrics') or {}
        base = {'result_json': data, 'metrics_json': metrics, 'finished_at': fields.Datetime.now(), 'state': 'done',
                'durations_json': {str(k): v for k, v in durations.items()},
                'error': False, 'wall_minutes': (metrics.get('wall_seconds') or 0) / 60,
                'peak_rss_mb': int(metrics.get('peak_child_rss_mb') or 0), 'worker_progress': 1}
        try:
            v = validate_report(split_highlights(data, durations)[0], durations, require_v2=True,
                                require_students=bool(self.roster_json),
                                roster=self.roster_json, planned_minutes=self.planned_minutes)
        except UserError as exc:
            return dict(base, state='failed', error=('invalid_result:%s' % exc)[:120])
        mapping = {'w_score_available': 'score_available', 'w_score_total': 'score_total',
                   'w_teaching_minutes': 'teaching_minutes', 'w_total_minutes': 'total_minutes',
                   'w_teaching_started_at': 'teaching_started_at', 'w_interaction_level': 'interaction_level',
                   'w_summary': 'summary', 'w_lesson_content': 'lesson_content', 'w_strengths': 'strengths',
                   'w_improvements': 'improvements', 'w_timing_note': 'timing_note', 'w_timing_details': 'timing_details',
                   'w_student_report': 'student_report', 'w_student_alert_count': 'student_alert_count',
                   'w_score_details': 'score_details'}
        return dict(base, **{ours: v.get(theirs) or False for ours, theirs in mapping.items() if ours != 'w_score_total'},
                    w_score_total=v.get('score_total') or 0)

    def _ack(self):
        try:
            response = self._worker('POST', '/v1/jobs/%s/ack' % self.job_key)
            self.acked = response.status_code in (200, 404)
        except ShadowError:
            pass  # the worker deletes the transcript after 72 hours anyway; retried next run

    def _advance(self, deadline):
        self.ensure_one()
        try:
            if self.state == 'upload':
                self._upload(deadline)
            elif self.state == 'waiting':
                self._poll()
            elif self.state == 'done' and not self.acked:
                self._finish()
            self.write({'failures': 0, 'next_check': False} if self.failures else {})
        except ShadowError as exc:
            failures = self.failures + 1
            give_up = not exc.retry or failures >= 6
            _logger.warning('review shadow %s step failed: %s', self.id, exc.code)
            self.write({'error': exc.code[:120], 'failures': failures, 'state': 'failed' if give_up else self.state,
                        'next_check': fields.Datetime.now() + timedelta(minutes=5 * 2 ** min(failures, 5))})
        except UserError as exc:  # Drive not connected etc.
            self.write({'error': str(exc)[:120], 'failures': self.failures + 1,
                        'next_check': fields.Datetime.now() + timedelta(minutes=30)})

    @staticmethod
    def _run_order(row):
        """Manager requests first, then official reports, then comparison runs; oldest first."""
        return (not row.priority, row.mode != 'official', row.id)

    @api.model
    def _cron_run(self):
        try:
            self._ready()
        except UserError:
            return
        cr = self.env.cr
        cr.execute('SELECT pg_try_advisory_lock(%s, 0)', [LOCK])
        if not cr.fetchone()[0]:
            return
        try:
            self._enqueue()
            cr.commit()
            if self._prefer_since():
                self._requeue_quota_failures()
                cr.commit()
                self._queue_official()
                cr.commit()
            now = fields.Datetime.now()
            rows = self.search([('state', 'in', ('upload', 'waiting', 'done')), ('acked', '=', False),
                                '|', ('next_check', '=', False), ('next_check', '<=', now)], order='id')
            rows = rows.sorted(self._run_order)
            deadline = time.monotonic() + STEP_SECONDS
            uploaded = False
            for row in rows:
                if row.state == 'upload':
                    # Strictly sequential: one video set on the worker at a time, one upload per run.
                    if uploaded or time.monotonic() > deadline or self.search_count([('state', '=', 'waiting')]):
                        continue
                    uploaded = True
                row._advance(deadline)
                cr.commit()
            if self._prefer_since():
                self._fallback_gemini()
                cr.commit()
        finally:
            cr.execute('SELECT pg_advisory_unlock(%s, 0)', [LOCK])

    @api.model
    def _fallback_gemini(self):
        """A finished-but-unusable official run gets ONE new Gemini request (decided once per row)."""
        rows = self.search([('mode', '=', 'official'), ('fallback_checked', '=', False),
                            '|', ('state', '=', 'failed'),
                            '&', ('state', '=', 'done'), '|', ('error', '=', FALLBACK_REASONS[0]),
                            ('error', '=like', FALLBACK_REASONS[1] + '%')], order='id')
        config = self.env.ref('edu_video.config_default').sudo()
        for row in rows:
            session = row.session_id.sudo()
            session.invalidate_recordset()
            reviews = session.ai_review_ids
            note = ('superseded' if self.search_count([('session_id', '=', session.id), ('mode', '=', 'official'),
                                                       ('id', '>', row.id)]) else
                    # Quota only: _requeue_quota_failures runs the session on the worker again instead.
                    'quota_requeue' if quota_failure(row) else
                    'already_reviewed' if session.ai_review_done else
                    'session_cancelled' if session.state == 'cancel' else
                    'gemini_active' if reviews.filtered(lambda r: r.state in ACTIVE) else
                    # A Gemini inference was sent and its answer lost: never create another attempt automatically.
                    'unknown_gemini_attempt' if reviews.filtered(
                        lambda r: r.analysis_started and not r.provider_response and not r.result_json) else
                    'gemini_disabled' if not (config.review_enabled and config.review_api_key) else False)
            review = self.env['edu.session.review']
            if not note:
                try:
                    with self.env.cr.savepoint():
                        review = session._queue_ai_review()
                    note = 'gemini_queued' if review.state in ACTIVE else 'gemini_%s' % review.state
                except UserError as exc:
                    note = ('gemini_error:%s' % exc)[:120]
            row.write({'fallback_checked': True, 'fallback_note': note, 'fallback_review_id': review.id or False})
            if note == 'gemini_queued':
                _logger.info('review worker row %s fell back to Gemini review %s', row.id, review.id)

    def action_retry(self):
        """Manager button: resume a failed upload/poll with the SAME job key (idempotent on the worker).
        A job the worker itself failed is never rerun from here: that would process the video twice."""
        for row in self.filtered(lambda r: r.state == 'failed'):
            if (row.error or '').startswith(('worker:', 'worker_cancelled', 'worker_expired', 'invalid_result')):
                raise UserError('Worker đã kết thúc tác vụ %s với lỗi; không tự chạy lại. '
                                'Kiểm tra log worker rồi quyết định thủ công.' % row.job_key)
            row.sudo().write({'state': 'waiting' if row.uploaded_mb and row.uploaded_mb >= row.total_mb else 'upload',
                              'failures': 0, 'next_check': False, 'error': False})
