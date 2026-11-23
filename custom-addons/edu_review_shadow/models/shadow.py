"""Shadow run of the internal review worker next to Gemini.

Never writes to edu.session.review, the session, attendance, payroll or week locks: the worker
result is stored here only, for comparison. Disabled until the cron is turned on and the
system parameters below are set.

  edu_review_shadow.worker_url     http://10.77.160.36:8090 (internal network only)
  edu_review_shadow.worker_token   bearer token from E:\\KimReview\\app\\.env.worker
  edu_review_shadow.enabled_since  'YYYY-MM-DD HH:MM:SS' UTC; only Gemini reports finished after it
  edu_review_shadow.daily_limit    new shadow jobs per day (default 20)

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
from odoo.addons.edu_video.models.job import parse_drive_url

_logger = logging.getLogger(__name__)
LOCK = 87426            # edu_session_review uses 87425
CHUNK = 32 * 1024 ** 2
STEP_SECONDS = 240      # upload budget shared by all records in one cron run; the cron runs every 5 minutes
PARAM = 'edu_review_shadow.'


class ShadowError(Exception):
    def __init__(self, code, retry=True):
        super().__init__(code)
        self.code, self.retry = code, retry


class ReviewShadow(models.Model):
    _name = 'edu.session.review.shadow'
    _description = 'Nhận xét AI song song (worker nội bộ)'
    _order = 'id desc'
    _rec_name = 'job_key'

    review_id = fields.Many2one('edu.session.review', 'Báo cáo Gemini', required=True, ondelete='cascade',
                                index=True, readonly=True)
    session_id = fields.Many2one(related='review_id.session_id', store=True, string='Buổi học')
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
        room = limit - self.search_count([('create_date', '>=', today)])
        if room <= 0:
            return self.browse()
        done = self.search([]).review_id.ids
        reviews = self.env['edu.session.review'].sudo().search(
            [('state', '=', 'done'), ('finished_at', '>=', since), ('id', 'not in', done)], order='finished_at', limit=room * 3)
        created = self.browse()
        for review in reviews:
            if len(created) >= room:
                break
            if not review.source_current or review.session_id.state == 'cancel':
                continue
            roster = review.roster_snapshot or review.session_id._review_roster()
            created |= self.create({'review_id': review.id, 'job_key': self.make_key(review, roster),
                                    'roster_json': roster})
        return created

    # ------------------------------------------------------------------ steps
    def _spec(self):
        review = self.review_id
        return {'roster': self.roster_json or [], 'prompt_version': review.prompt_version or '2.1',
                'planned_minutes': review.planned_minutes or 0,
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
        if self.review_id.source_signature != self.session_id._review_signature():
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
            self._ack()

    def _result_values(self, job):
        review = self.review_id
        data = job.get('result') or {}
        durations = {int(k): float(v) for k, v in (job.get('durations') or {}).items()}
        metrics = job.get('metrics') or {}
        base = {'result_json': data, 'metrics_json': metrics, 'finished_at': fields.Datetime.now(), 'state': 'done',
                'error': False, 'wall_minutes': (metrics.get('wall_seconds') or 0) / 60,
                'peak_rss_mb': int(metrics.get('peak_child_rss_mb') or 0), 'worker_progress': 1}
        try:
            v = validate_report(data, durations, require_v2=True, require_students=bool(self.roster_json),
                                roster=self.roster_json, planned_minutes=review.planned_minutes)
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
                self._ack()
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
            now = fields.Datetime.now()
            rows = self.search([('state', 'in', ('upload', 'waiting', 'done')), ('acked', '=', False),
                                '|', ('next_check', '=', False), ('next_check', '<=', now)], order='id')
            deadline = time.monotonic() + STEP_SECONDS
            for row in rows:
                if row.state == 'upload' and time.monotonic() > deadline:
                    continue  # polling is cheap; uploads wait for the next run
                row._advance(deadline)
                cr.commit()
        finally:
            cr.execute('SELECT pg_advisory_unlock(%s, 0)', [LOCK])

    def action_retry(self):
        """Manager button: resume a failed upload/poll with the SAME job key (idempotent on the worker).
        A job the worker itself failed is never rerun from here: that would process the video twice."""
        for row in self.filtered(lambda r: r.state == 'failed'):
            if (row.error or '').startswith(('worker:', 'worker_cancelled', 'worker_expired', 'invalid_result')):
                raise UserError('Worker đã kết thúc tác vụ %s với lỗi; không tự chạy lại. '
                                'Kiểm tra log worker rồi quyết định thủ công.' % row.job_key)
            row.sudo().write({'state': 'waiting' if row.uploaded_mb and row.uploaded_mb >= row.total_mb else 'upload',
                              'failures': 0, 'next_check': False, 'error': False})
