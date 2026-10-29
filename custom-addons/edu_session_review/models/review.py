import hashlib
import json
import math
import re
import shutil
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import config as server_config

from .report import PROMPT, clock, generation_schema, validate_report

API = 'https://generativelanguage.googleapis.com'
CHUNK = 8 * 1024 * 1024
LOCK = 87425
STATES = [('queued', 'Chờ phân tích'), ('processing', 'Đang xử lý video'),
          ('analyzing', 'Gemini đang phân tích'), ('done', 'Đã có nhận xét'),
          ('failed', 'Lỗi'), ('cancelled', 'Đã hủy')]


class ReviewError(Exception):
    def __init__(self, message, retry=False):
        super().__init__(message)
        self.retry = retry


def safe_upload_url(url):
    parsed = urlparse(url or '')
    try:
        valid = (parsed.scheme == 'https' and parsed.hostname == 'generativelanguage.googleapis.com'
                 and parsed.path.startswith('/upload/') and not parsed.username and not parsed.password
                 and parsed.port in (None, 443))
    except ValueError:
        valid = False
    if not valid:
        raise UserError('Gemini trả về địa chỉ upload không hợp lệ.')
    return url


def file_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'files/[a-z0-9-]{1,80}', value):
        raise UserError('Gemini trả về mã file không hợp lệ.')
    return value


class SessionReview(models.Model):
    _name = 'edu.session.review'
    _description = 'Nhận xét AI buổi học'
    _order = 'id desc'
    _rec_name = 'name'

    name = fields.Char('Báo cáo', default='Nhận xét AI', required=True)
    session_id = fields.Many2one('edu.session', 'Buổi học', required=True, ondelete='restrict', index=True)
    source_signature = fields.Char(index=True)
    model_name = fields.Char('Model sử dụng', required=True)
    prompt_version = fields.Char('Phiên bản tiêu chí', default='2.0', readonly=True)
    state = fields.Selection(STATES, string='Trạng thái', default='queued', required=True, index=True)
    requested_by = fields.Many2one('res.users', 'Người yêu cầu', default=lambda self: self.env.user, readonly=True)
    part_ids = fields.One2many('edu.session.review.part', 'review_id')
    finished_at = fields.Datetime('Hoàn tất lúc', readonly=True)
    error = fields.Text('Lỗi phân tích', readonly=True)
    attempts = fields.Integer(readonly=True)
    next_attempt = fields.Datetime(readonly=True)
    analysis_started = fields.Boolean(copy=False)
    cleanup_pending = fields.Boolean('Chờ dọn dữ liệu tạm', default=False, copy=False)
    summary = fields.Text('Nhận xét tổng quát', readonly=True)
    sufficient_data = fields.Boolean('Đủ dữ liệu ước lượng thời gian', readonly=True)
    quality_note = fields.Text('Chất lượng bản ghi / giới hạn', readonly=True)
    total_minutes = fields.Float('Tổng thời lượng video (phút)', readonly=True, digits=(12, 2))
    teaching_minutes = fields.Float('Dạy/học thực tế ước lượng (phút)', readonly=True, digits=(12, 2))
    teaching_percent = fields.Float('Tỷ lệ hoạt động dạy/học ước lượng (%)', readonly=True, digits=(12, 1))
    interaction_level = fields.Selection([
        ('low', 'Thấp'), ('medium', 'Trung bình'), ('good', 'Tốt'),
        ('insufficient', 'Chưa đủ dữ liệu')], string='Mức độ tương tác', readonly=True)
    interaction_comment = fields.Text('Nhận xét tương tác', readonly=True)
    strengths = fields.Text('Điểm mạnh và dẫn chứng', readonly=True)
    improvements = fields.Text('Điểm cần cải thiện và dẫn chứng', readonly=True)
    lesson_content = fields.Text('Nội dung đã dạy', readonly=True)
    timing_note = fields.Text('Căn cứ xác định thời gian', readonly=True)
    teaching_started_at = fields.Char('Bắt đầu giảng dạy', readonly=True)
    timing_details = fields.Text('Các khoảng giảng dạy', readonly=True)
    score_available = fields.Boolean('Có điểm đánh giá', readonly=True)
    score_total = fields.Float('Điểm chất lượng / 10', readonly=True, digits=(4, 1))
    score_content = fields.Float('Nội dung / 2,5', readonly=True, digits=(3, 1))
    score_instruction = fields.Float('Hướng dẫn / 2,5', readonly=True, digits=(3, 1))
    score_interaction = fields.Float('Tương tác / 2,5', readonly=True, digits=(3, 1))
    score_management = fields.Float('Tổ chức / 2,5', readonly=True, digits=(3, 1))
    score_details = fields.Text('Căn cứ chấm điểm', readonly=True)
    score_display = fields.Char(compute='_compute_report_display')
    time_display = fields.Char(compute='_compute_report_display')
    ratio_display = fields.Char(compute='_compute_report_display')
    result_json = fields.Json(readonly=True)
    source_current = fields.Boolean('Khớp các link Drive hiện tại', compute='_compute_source_current')

    @api.depends('score_available', 'score_total', 'sufficient_data', 'teaching_minutes', 'total_minutes',
                 'teaching_percent', 'state')
    def _compute_report_display(self):
        for review in self:
            review.score_display = ('%.1f / 10' % review.score_total) if review.score_available else 'Chưa có điểm'
            review.time_display = ('%s / %s' % (clock(review.teaching_minutes * 60), clock(review.total_minutes * 60))) \
                if review.sufficient_data else 'Chưa đủ dữ liệu'
            review.ratio_display = ('%.1f%% thời lượng video' % review.teaching_percent) \
                if review.sufficient_data else 'Chưa thể ước lượng'

    def action_reanalyze(self):
        self.ensure_one()
        self._manager()
        return self.session_id.action_analyze_lesson()

    @api.depends('session_id.google_drive_url', 'session_id.recording_part_ids.google_drive_url', 'source_signature')
    def _compute_source_current(self):
        for review in self:
            review.source_current = review.source_signature == review.session_id._review_signature()

    def _manager(self):
        if not self.env.user.has_group('edu_gvnn.group_edu_manager'):
            raise AccessError('Chỉ quản lý GVNN được phân tích hoặc hủy nhận xét AI.')
        self.check_access_rights('read')
        self.check_access_rule('read')

    def _config(self):
        return self.env.ref('edu_video.config_default').sudo()

    def _checkpoint(self):
        # Called only by the background worker; tests replace this method.
        self.env.cr.commit()

    def _gemini(self, method, path, **kwargs):
        headers = dict(kwargs.pop('extra_headers', {}))
        headers['x-goog-api-key'] = self._config().review_api_key
        timeout = kwargs.pop('request_timeout', (10, 45))
        response = requests.request(method, API + path,
            headers=headers,
            timeout=timeout, allow_redirects=False, **kwargs)
        if response.status_code == 404 and method == 'DELETE':
            return response
        if not 200 <= response.status_code < 300:
            status = response.status_code
            response.close()
            raise ReviewError('Gemini HTTP %s. Kiểm tra API key, model, hạn mức và quyền dự án.' % status,
                              retry=status in (429, 500, 502, 503, 504))
        return response

    def _durations(self):
        return {part.number: part.duration for part in self.part_ids}

    def _apply_result(self, response):
        candidates = response.get('candidates') or []
        if len(candidates) != 1 or candidates[0].get('finishReason') != 'STOP':
            raise UserError('Gemini chưa trả đủ nhận xét hoặc đã dừng vì giới hạn nội dung. Hãy kiểm tra rồi phân tích lại.')
        content = candidates[0].get('content', {}).get('parts', [])
        text = ''.join(item.get('text', '') for item in content if not item.get('thought'))
        data = json.loads(text)
        # Keep the response for diagnosis/revalidation without another paid request.
        # This field has the same manager-only ACL as the rest of the review.
        self.result_json = data
        values = validate_report(data, self._durations(), require_v2=self.prompt_version == '2.0')
        self.write(dict(values, state='done', result_json=data, finished_at=fields.Datetime.now(),
                        error=False, cleanup_pending=True))

    def _step(self):
        self.ensure_one()
        config = self._config()
        config._review_ready()
        if self.source_signature != self.session_id._review_signature():
            raise UserError('Các link Drive đã thay đổi. Hãy phân tích lại các video hiện tại.')
        if self.session_id.state == 'cancel':
            raise UserError('Buổi học đã nghỉ; không tiếp tục gửi video để phân tích.')
        unknown = self.part_ids.filtered(lambda item: not item.total_bytes)[:1]
        if unknown:
            # Check the whole lesson's size before downloading/uploading any part.
            unknown._metadata()
            return True
        part = self.part_ids.filtered(lambda item: item.state != 'ready')[:1]
        if part:
            self.state = 'processing'
            return part._step()
        if sum(self.part_ids.mapped('duration')) > config.review_max_minutes * 60:
            raise UserError('Tổng thời lượng vượt giới hạn phân tích đã cấu hình.')
        if self.state != 'analyzing':
            # Start the inference in a fresh cron invocation, leaving time for its response.
            self.state = 'analyzing'
            return False
        if self.analysis_started:
            raise UserError('Yêu cầu Gemini trước chưa được xác nhận. Hãy tạo lần phân tích mới để tránh gửi lặp tự động.')
        self.analysis_started = True
        self._checkpoint()
        try:
            with self._gemini('POST', '/v1beta/models/' + self.model_name + ':generateContent',
                              json=self._analysis_payload(), request_timeout=(10, 90)) as response:
                result = response.json()
        except ReviewError:
            # An explicit rejected HTTP request is safe to retry; a lost response is not.
            self.analysis_started = False
            raise
        self._apply_result(result)
        return True

    def _analysis_payload(self):
        parts = [{'text': PROMPT}]
        for item in self.part_ids.sorted('number'):
            parts.extend([
                {'text': 'Phần %s; thời lượng %s (%.3f giây). start/end dùng chuỗi MM:SS từ 00:00, '
                         'không vượt thời lượng này.' % (item.number, clock(math.floor(item.duration)), item.duration)},
                {'fileData': {'fileUri': item.gemini_uri, 'mimeType': item.mime_type}},
            ])
        generation = {
            'temperature': 0.2, 'maxOutputTokens': 8192,
            'responseMimeType': 'application/json', 'responseJsonSchema': generation_schema(),
        }
        if self.model_name.startswith('gemini-3'):
            generation['thinkingConfig'] = {'thinkingLevel': 'low'}
        return {'contents': [{'role': 'user', 'parts': parts}], 'generationConfig': generation}

    def _cleanup(self):
        """Delete only this review's temporary files. Never touch the upload cache."""
        complete = True
        for part in self.part_ids:
            part._remove_local()
        for part in self.part_ids:
            if part.gemini_name:
                try:
                    with self._gemini('DELETE', '/v1beta/' + file_name(part.gemini_name)):
                        pass
                    part.gemini_name = False
                except (ReviewError, requests.RequestException, UserError):
                    complete = False
                    break
        self.cleanup_pending = not complete

    def action_cancel(self):
        self._manager()
        for review in self:
            self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', [LOCK, review.id])
            if not self.env.cr.fetchone()[0]:
                raise UserError('Tác vụ đang xử lý. Hãy thử hủy sau ít phút.')
            if review.state not in ('done', 'cancelled'):
                review.sudo().write({'state': 'cancelled', 'cleanup_pending': True})

    @api.model
    def _cron_process(self):
        config = self.env.ref('edu_video.config_default').sudo()
        # A clone/neutralized DB must never send data, even if a copied key exists.
        neutralized = self.env['ir.config_parameter'].sudo().get_param('database.is_neutralized')
        if str(neutralized).lower() in ('true', '1', 'yes') or not config.review_enabled or not config.review_api_key:
            return
        self.env.cr.execute('SELECT pg_try_advisory_lock(%s, 0)', [LOCK])
        if not self.env.cr.fetchone()[0]:
            return
        try:
            cleanup = self.sudo().search([('cleanup_pending', '=', True),
                ('state', 'in', ['done', 'failed', 'cancelled']),
                '|', ('next_attempt', '=', False), ('next_attempt', '<=', fields.Datetime.now())], limit=1)
            if cleanup:
                try:
                    cleanup._cleanup()
                except OSError:
                    cleanup.cleanup_pending = True
                cleanup.next_attempt = fields.Datetime.now() + timedelta(hours=1)
                cleanup._checkpoint()
            review = self.sudo().search([('state', 'in', ['queued', 'processing', 'analyzing']),
                '|', ('next_attempt', '=', False), ('next_attempt', '<=', fields.Datetime.now())], order='id', limit=1)
            if not review:
                return
            self.env.cr.execute('SELECT pg_try_advisory_lock(%s, %s)', [LOCK, review.id])
            if not self.env.cr.fetchone()[0]:
                return
            try:
                deadline = time.monotonic() + 35
                while time.monotonic() < deadline:
                    review.invalidate_recordset()
                    config.invalidate_recordset()
                    if review.state not in ('queued', 'processing', 'analyzing') or not config.review_enabled:
                        break
                    if review.create_date < fields.Datetime.now() - timedelta(hours=24):
                        raise UserError('Tác vụ phân tích quá 24 giờ. Hãy kiểm tra và phân tích lại.')
                    progressed = review._step()
                    review.write({'attempts': 0, 'next_attempt': False, 'error': False})
                    review._checkpoint()
                    if review.state == 'done' or not progressed:
                        break
            except (ReviewError, requests.RequestException, UserError, ValueError, KeyError, TypeError, OSError) as exc:
                retry = (isinstance(exc, requests.RequestException) or isinstance(exc, ReviewError) and exc.retry)
                # An unconfirmed analysis POST can incur cost: do not repeat it automatically.
                retry = retry and not review.analysis_started
                attempts = review.attempts + 1
                retry = retry and attempts <= 3
                message = str(exc) if isinstance(exc, (ReviewError, UserError)) else 'Lỗi kết nối/dữ liệu phân tích. Kiểm tra cấu hình rồi thử lại.'
                review.write({'state': review.state if retry else 'failed', 'attempts': attempts,
                    'error': message, 'cleanup_pending': not retry,
                    'next_attempt': fields.Datetime.now() + timedelta(minutes=2 ** attempts) if retry else False})
                review._checkpoint()
            finally:
                self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', [LOCK, review.id])
        finally:
            self.env.cr.execute('SELECT pg_advisory_unlock(%s, 0)', [LOCK])

    @api.model
    def _cron_cleanup(self):
        deadline = time.monotonic() + 35
        expired = fields.Datetime.now() - timedelta(hours=24)
        reviews = self.sudo().search(['|', ('next_attempt', '=', False), ('next_attempt', '<=', fields.Datetime.now()),
            '|', ('cleanup_pending', '=', True),
            '&', ('create_date', '<', expired), ('state', 'in', ['queued', 'processing', 'analyzing'])], limit=20)
        for review in reviews:
            if time.monotonic() > deadline:
                break
            self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', [LOCK, review.id])
            if not self.env.cr.fetchone()[0]:
                continue
            if review.state in ('queued', 'processing', 'analyzing'):
                review.write({'state': 'failed', 'error': 'Tác vụ quá 24 giờ; hãy phân tích lại.', 'cleanup_pending': True})
            if review._config().review_api_key:
                try:
                    review._cleanup()
                except OSError:
                    pass
                if review.cleanup_pending:
                    review.next_attempt = fields.Datetime.now() + timedelta(hours=1)
            else:
                for part in review.part_ids:
                    try:
                        part._remove_local()
                    except OSError:
                        pass


class ReviewPart(models.Model):
    _name = 'edu.session.review.part'
    _description = 'Video nguồn của nhận xét AI'
    _order = 'number'

    review_id = fields.Many2one('edu.session.review', required=True, ondelete='cascade')
    number = fields.Integer('Phần', required=True)
    source_url = fields.Char('Link Drive', required=True)
    file_id = fields.Char(required=True, groups='base.group_no_one')
    resource_key = fields.Char(groups='base.group_no_one')
    state = fields.Selection([('download', 'Tải Drive'), ('upload', 'Gửi Gemini'),
        ('waiting', 'Gemini xử lý'), ('ready', 'Sẵn sàng')], string='Trạng thái', default='download', required=True)
    total_bytes = fields.Float(digits=(20, 0))
    mime_type = fields.Char()
    checksum = fields.Char(groups='base.group_no_one')
    upload_url = fields.Char(groups='base.group_no_one', copy=False)
    gemini_name = fields.Char(groups='base.group_no_one', copy=False)
    gemini_uri = fields.Char(groups='base.group_no_one', copy=False)
    duration = fields.Float('Thời lượng (giây)', digits=(16, 3))

    def _path(self):
        self.ensure_one()
        root = Path(server_config['data_dir']) / 'edu_session_review'
        uuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid', '')
        digest = hashlib.sha256((self.env.cr.dbname + uuid).encode()).hexdigest()[:24]
        folder = root / digest
        if root.is_symlink() or folder.is_symlink():
            raise UserError('Thư mục tạm nhận xét AI không hợp lệ.')
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = folder / ('%s.video' % self.id)
        if path.is_symlink():
            raise UserError('File tạm nhận xét AI không hợp lệ.')
        return path

    def _remove_local(self):
        self._path().unlink(missing_ok=True)

    def _drive(self, **kwargs):
        config = self.review_id._config()
        headers = kwargs.pop('headers', {})
        if self.resource_key:
            headers['X-Goog-Drive-Resource-Keys'] = '%s/%s' % (self.file_id, self.resource_key)
        for attempt in range(2):
            headers['Authorization'] = 'Bearer ' + config._token('drive', force=bool(attempt))
            response = requests.get('https://www.googleapis.com/drive/v3/files/' + self.file_id,
                headers=headers, timeout=(10, 45), allow_redirects=False, **kwargs)
            if response.status_code != 401:
                break
            response.close()
        if response.status_code not in (200, 206):
            status = response.status_code
            response.close()
            raise ReviewError('Không tải được video Drive (HTTP %s).' % status, status in (429, 500, 502, 503))
        return response

    def _metadata(self):
        with self._drive(params={'fields': 'size,mimeType,md5Checksum,capabilities(canDownload)',
                                 'supportsAllDrives': 'true'}) as response:
            info = response.json()
        size = int(info.get('size', 0))
        config = self.review_id._config()
        total = sum((self.review_id.part_ids - self).mapped('total_bytes')) + size
        if not 0 < size or total > config.review_max_mb * 1024 ** 2:
            raise UserError('Tổng dung lượng video vượt giới hạn phân tích hoặc file rỗng.')
        if not info.get('mimeType', '').startswith('video/') or not info.get('capabilities', {}).get('canDownload') or not info.get('md5Checksum'):
            raise UserError('Drive chưa sẵn sàng hoặc tài khoản không được tải file video này.')
        self.write({'total_bytes': size, 'mime_type': info['mimeType'], 'checksum': info['md5Checksum']})

    def _download(self):
        if not self.total_bytes:
            self._metadata()
            return True
        path = self._path()
        start = path.stat().st_size if path.exists() else 0
        total = int(self.total_bytes)
        if start > total:
            raise UserError('File tạm vượt dung lượng nguồn. Hãy phân tích lại.')
        if start < total:
            end = min(start + CHUNK, total) - 1
            if shutil.disk_usage(path.parent).free < (end - start + 1) + 256 * 1024 ** 2:
                raise UserError('Máy chủ không đủ dung lượng tạm để phân tích.')
            with self._drive(params={'alt': 'media', 'supportsAllDrives': 'true'},
                             headers={'Range': 'bytes=%s-%s' % (start, end)}, stream=True) as response:
                if response.status_code != 206 or response.headers.get('Content-Range') != 'bytes %s-%s/%s' % (start, end, total):
                    raise UserError('Drive trả về khoảng dữ liệu không khớp; chưa ghi file.')
                # Bound memory and disk even if an upstream ignores Range/content length.
                data = response.raw.read(end - start + 2)
                if len(data) != end - start + 1:
                    raise UserError('Dữ liệu video không đủ hoặc vượt khoảng tải yêu cầu.')
            with path.open('ab') as output:
                output.write(data)
            return True
        digest = hashlib.md5()
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(CHUNK), b''):
                digest.update(chunk)
        if digest.hexdigest() != self.checksum:
            raise UserError('Video Drive đã thay đổi hoặc tải không toàn vẹn. Hãy phân tích lại.')
        self.state = 'upload'
        return True

    def _accept_file(self, data):
        info = data.get('file', data)
        name = file_name(info.get('name'))
        uri = info.get('uri', '')
        if uri != API + '/v1beta/' + name:
            raise UserError('Gemini trả về URI file không hợp lệ.')
        self.write({'gemini_name': name, 'gemini_uri': uri, 'state': 'waiting', 'upload_url': False})
        self._remove_local()

    def _display_name(self):
        uuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid', '')
        return 'kim-review-%s-%s' % (hashlib.sha256(uuid.encode()).hexdigest()[:12], self.id)

    def _upload(self):
        review = self.review_id
        if not self.upload_url:
            with review._gemini('POST', '/upload/v1beta/files', json={'file': {'display_name': self._display_name()}},
                    extra_headers={'X-Goog-Upload-Protocol': 'resumable', 'X-Goog-Upload-Command': 'start',
                        'X-Goog-Upload-Header-Content-Length': str(int(self.total_bytes)),
                        'X-Goog-Upload-Header-Content-Type': self.mime_type}) as response:
                self.upload_url = safe_upload_url(response.headers.get('X-Goog-Upload-URL'))
            return True
        url = safe_upload_url(self.upload_url)
        suffix = url[len(API):]
        with review._gemini('POST', suffix, data=b'', extra_headers={'X-Goog-Upload-Command': 'query'}) as response:
            status = response.headers.get('X-Goog-Upload-Status')
            offset = int(response.headers.get('X-Goog-Upload-Size-Received', '-1'))
        if status == 'final':
            token = None
            for _ in range(10):
                with review._gemini('GET', '/v1beta/files', params={'pageSize': 100, **({'pageToken': token} if token else {})}) as response:
                    page = response.json()
                found = next((item for item in page.get('files', []) if item.get('displayName') == self._display_name()), None)
                if found:
                    self._accept_file(found)
                    return True
                token = page.get('nextPageToken')
                if not token:
                    break
            raise UserError('Phiên Gemini đã hoàn tất nhưng chưa tìm thấy file. Hãy phân tích lại.')
        total = int(self.total_bytes)
        if status != 'active' or not 0 <= offset <= total:
            raise UserError('Phiên upload Gemini không còn hợp lệ. Hãy phân tích lại.')
        with self._path().open('rb') as source:
            source.seek(offset)
            chunk = source.read(CHUNK)
        final = offset + len(chunk) == total
        with review._gemini('POST', suffix, data=chunk, extra_headers={
                'X-Goog-Upload-Offset': str(offset), 'X-Goog-Upload-Command': 'upload, finalize' if final else 'upload',
                'Content-Type': self.mime_type}) as response:
            if final:
                self._accept_file(response.json())
        return True

    def _step(self):
        if self.state == 'download':
            return self._download()
        if self.state == 'upload':
            return self._upload()
        with self.review_id._gemini('GET', '/v1beta/' + file_name(self.gemini_name)) as response:
            info = response.json()
        if info.get('state') == 'ACTIVE':
            raw_duration = info.get('videoMetadata', {}).get('videoDuration', '')
            if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?s', raw_duration):
                raise UserError('Gemini chưa trả thời lượng video; không thể tính tỷ lệ dạy/học.')
            duration = float(raw_duration[:-1])
            if not math.isfinite(duration) or duration <= 0:
                raise UserError('Thời lượng video không hợp lệ.')
            self.write({'state': 'ready', 'duration': duration})
            return True
        if info.get('state') != 'PROCESSING':
            raise UserError('Gemini không xử lý được video nguồn.')
        return False
