import hashlib
import logging
import os
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import config as server_config

CHUNK = 8 * 1024 * 1024
LOCK_NAMESPACE = 87421
ACTIVE = ['queued', 'downloading', 'uploading']
JOB_STATES = [
    ('queued', 'Chờ xử lý'), ('downloading', 'Đang tải Drive'), ('uploading', 'Đang gửi YouTube'),
    ('done', 'Đã tải lên'), ('failed', 'Lỗi'), ('uncertain', 'Cần kiểm tra YouTube'), ('cancelled', 'Đã hủy')]
_logger = logging.getLogger(__name__)


def parse_drive_url(url):
    try:
        parsed = urlparse((url or '').strip())
        port = parsed.port
    except ValueError:
        raise UserError('Link Drive không hợp lệ.')
    if (parsed.scheme != 'https' or parsed.hostname != 'drive.google.com'
            or parsed.username or parsed.password or port not in (None, 443)):
        raise UserError('Cần link HTTPS của một file video trên drive.google.com.')
    query = parse_qs(parsed.query)
    match = re.fullmatch(r'/file/d/([\w-]+)(?:/[^/]*)?/?', parsed.path)
    file_id = match.group(1) if match else (query.get('id', [''])[0] if parsed.path in ('/open', '/uc') else '')
    key = query.get('resourcekey', [''])[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', file_id) or (key and not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', key)):
        raise UserError('Link Drive không hợp lệ. Hãy dùng link chia sẻ của file, không dùng link thư mục.')
    return file_id, key


class TransferError(Exception):
    def __init__(self, message, retry=False, uncertain=False):
        super().__init__(message)
        self.retry = retry
        self.uncertain = uncertain


class EduVideoJob(models.Model):
    _name = 'edu.video.job'
    _description = 'Xử lý video buổi học'
    _order = 'id desc'
    _rec_name = 'title'

    session_id = fields.Many2one('edu.session', 'Buổi học', required=True, ondelete='restrict', index=True)
    recording_part_id = fields.Many2one('edu.session.recording.part', 'Đoạn bổ sung', ondelete='restrict', readonly=True, index=True)
    part_number = fields.Integer('Phần', compute='_compute_part_number')

    @api.depends('recording_part_id.number')
    def _compute_part_number(self):
        for job in self:
            job.part_number = job.recording_part_id.number if job.recording_part_id else 1

    def _recording_target(self):
        self.ensure_one()
        return self.recording_part_id or self.session_id
    title = fields.Char('Tiêu đề YouTube', required=True, default='Video buổi học GVNN')
    description = fields.Text('Mô tả YouTube', readonly=True, copy=False)
    source_url = fields.Char('Link Drive', required=True, readonly=True)
    file_id = fields.Char(required=True, readonly=True, index=True)
    resource_key = fields.Char(groups='base.group_no_one')
    state = fields.Selection(JOB_STATES, default='queued', required=True, readonly=True, index=True)
    error = fields.Text('Chi tiết / lỗi', readonly=True)
    video_url = fields.Char('Video YouTube', readonly=True)
    finished_at = fields.Datetime('Hoàn tất', readonly=True)
    cache_started_at = fields.Datetime('Bắt đầu lưu video tạm', readonly=True, copy=False)
    cache_expired = fields.Boolean('Đã hết hạn lưu file tạm', readonly=True, copy=False)
    # PostgreSQL INTEGER cannot hold videos > 2GB; store byte counts as numeric floats (exact up to 2^53).
    total_bytes = fields.Float('Dung lượng (byte)', digits=(20, 0), readonly=True)
    uploaded_bytes = fields.Float('Đã gửi (byte)', digits=(20, 0), readonly=True)
    progress = fields.Float('Tiến độ gửi (%)', compute='_compute_progress')
    mime_type = fields.Char(readonly=True)
    checksum = fields.Char(readonly=True, groups='base.group_no_one')
    upload_url = fields.Char(groups='base.group_no_one', copy=False)
    channel_id = fields.Char('Channel ID đích', readonly=True)
    attempts = fields.Integer('Số lỗi tạm thời', readonly=True)
    next_attempt = fields.Datetime('Lần xử lý tiếp', readonly=True)

    _sql_constraints = [('session_file_unique', 'unique(session_id, file_id)',
                         'File này đã có trong lịch sử xử lý của buổi học.')]

    @api.depends('total_bytes', 'uploaded_bytes', 'state')
    def _compute_progress(self):
        for job in self:
            job.progress = 100 if job.state == 'done' else (100 * job.uploaded_bytes / job.total_bytes if job.total_bytes else 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            session = self.env['edu.session'].browse(vals['session_id'])
            if vals.get('recording_part_id'):
                part = self.env['edu.session.recording.part'].browse(vals['recording_part_id'])
                if part.session_id != session:
                    raise UserError('Recording part does not belong to this lesson.')
            vals.setdefault('title', self._youtube_title(
                session, part if vals.get('recording_part_id') else None))
            vals.setdefault('description', self._youtube_description(session))
        return super().create(vals_list)

    @api.model
    def _youtube_title(self, session, part=None, strict=False):
        teacher = session.teacher_id
        salutation = {'mr': 'MR', 'ms': 'MS'}.get(teacher.teaching_title, '')
        names = [' '.join((a.student_id.name_en or a.student_id.name_vi or '').split()).title()
                 for a in session.attendee_ids]
        names = [name for name in names if name]
        if not names and session.extra_participants:
            names = [' '.join(session.extra_participants.split()).title()]
        if strict:
            if not salutation:
                raise UserError('Hãy chọn danh xưng Thầy/Cô trong hồ sơ giáo viên để tạo tiêu đề MR/MS.')
            if not session.week_id:
                raise UserError('Buổi học chưa có tuần. Hãy chọn tuần trước khi upload YouTube.')
            if not names:
                raise UserError('Buổi học chưa có tên học sinh để tạo tiêu đề YouTube.')
        teacher_name = ' '.join(teacher.name.split()).upper()
        label = ' '.join(filter(None, [salutation, teacher_name]))
        week = session.week_id.number if session.week_id else '?'
        title = 'KIMENGLISH - %s - %s (WEEK %s)' % (label, ' & '.join(names) or '?', week)
        if sum(bool(p['drive'] or p['youtube']) for p in session._recording_parts()) > 1:
            title += ' (%s)' % (part.number if part else 1)
        if strict and (len(title) > 100 or '<' in title or '>' in title):
            raise UserError('Tiêu đề YouTube tối đa 100 ký tự và không chứa dấu < hoặc >. Hãy kiểm tra tên hiển thị giáo viên/học sinh.')
        return title

    def _refresh_upload_title(self):
        self.ensure_one()
        # A resumable session already contains its metadata; never change it mid-transfer.
        if not self.upload_url:
            self.write({
                'title': self._youtube_title(self.session_id, self.recording_part_id or None, strict=True),
                'description': self._youtube_description(self.session_id),
            })

    @api.model
    def _youtube_description(self, session):
        weekdays = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật']
        def clock(value):
            return '%02d:%02d' % divmod(round(value * 60) % 1440, 60)
        lesson_time = ('%s–%s' % (clock(session.time_start), clock(session.time_end))
                       if session.time_start or session.time_end else 'Chưa cập nhật')
        return '%s %s %s' % (
            lesson_time, weekdays[session.date.weekday()], session.date.strftime('%d/%m/%Y'))

    @api.model
    def _cache_folder(self):
        db_key = hashlib.sha256(self.env.cr.dbname.encode()).hexdigest()[:20]
        return Path(server_config['data_dir']) / 'edu_video' / db_key

    def _path(self):
        self.ensure_one()
        folder = self._cache_folder()
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        return folder / ('%s.video' % self.id)

    def _cleanup(self):
        path = self._path()
        try:
            path.unlink(missing_ok=True)
        except OSError:
            _logger.warning('Could not remove temporary video for job %s', self.id)

    @api.model
    def _cron_cleanup_video_cache(self):
        """Remove only this database's numbered cache files, never Drive files or attachments."""
        folder = self._cache_folder()
        root = Path(server_config['data_dir']) / 'edu_video'
        if (not folder.is_dir() or folder.is_symlink()
                or folder.resolve().parent != root.resolve()):
            return 0
        cutoff = fields.Datetime.now() - timedelta(days=7)
        removed = 0
        for path in folder.iterdir():
            if not re.fullmatch(r'[1-9][0-9]*\.video', path.name) or path.is_symlink() or not path.is_file():
                continue
            job_id = int(path.stem)
            if job_id > 2147483647:
                continue
            self.env.cr.execute('SELECT pg_try_advisory_lock(%s, %s)', [LOCK_NAMESPACE, job_id])
            if not self.env.cr.fetchone()[0]:
                continue  # A worker owns this file; retry on the next sweep.
            try:
                job = self.sudo().browse(job_id).exists()
                if job:
                    job.invalidate_recordset()
                    started = job.cache_started_at or job.create_date
                else:
                    # Orphan files have no job timestamp; use their last modification time.
                    started = datetime.utcfromtimestamp(path.stat().st_mtime)
                if started > cutoff:
                    continue
                if job:
                    vals = {'cache_expired': True, 'next_attempt': False}
                    if job.state not in ('done', 'cancelled'):
                        vals['state'] = 'uncertain' if job.upload_url else 'cancelled'
                    if not job.cache_expired:
                        message = 'File video tạm đã hết hạn lưu 7 ngày. Yêu cầu đã dừng để dọn file tự động.'
                        if job.upload_url and job.state != 'done':
                            message += ' Kiểm tra YouTube trước khi tạo phiên upload mới.'
                        vals['error'] = '\n'.join(filter(None, [job.error, message]))
                    job.write(vals)
                    # Persist the stop before deleting bytes. Session advisory lock survives commit.
                    job._checkpoint()
                path.unlink(missing_ok=True)
                removed += 1
            except OSError:
                _logger.warning('Could not expire temporary video for job %s', job_id)
            finally:
                self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', [LOCK_NAMESPACE, job_id])
        _logger.info('Expired %s temporary video files for this database', removed)
        return removed

    def _checkpoint(self):
        # Only the cron entry point calls this in production. Tests replace this method.
        self.env.cr.commit()

    def _cache_is_expired(self):
        self.ensure_one()
        return bool(self.cache_expired or (self.cache_started_at and
                    self.cache_started_at <= fields.Datetime.now() - timedelta(days=7)))

    def _request(self, service, method, url, **kwargs):
        c = self.env.ref('edu_video.config_default').sudo()
        headers = dict(kwargs.pop('headers', {}))
        for retry in range(2):
            headers['Authorization'] = 'Bearer ' + c._token(service, force=bool(retry))
            response = requests.request(method, url, headers=headers, timeout=(15, 45), **kwargs)
            if response.status_code != 401:
                break
            response.close()
        if response.status_code in (200, 201, 206, 308):
            return response
        status = response.status_code
        response.close()
        if self.upload_url and status in (404, 410) and service == 'youtube':
            raise TransferError('Phiên upload đã hết hạn. Kiểm tra kênh YouTube trước khi tạo yêu cầu mới để tránh trùng video.', uncertain=True)
        raise TransferError('%s trả về HTTP %s. Kiểm tra quyền, dung lượng hoặc hạn mức API.' % (service, status),
                            retry=status == 429 or status >= 500)

    def _guard(self):
        self.invalidate_recordset()
        if self._cache_is_expired():
            raise TransferError('Video tạm đã hết hạn lưu 7 ngày. Kiểm tra lịch sử trước khi thử lại.',
                                uncertain=bool(self.upload_url))
        c = self.env.ref('edu_video.config_default').sudo()
        c.invalidate_recordset()
        c._ready()
        if self.channel_id and self.channel_id != c.channel_id:
            raise TransferError('Kênh YouTube đã thay đổi. Không thể tiếp tục phiên upload của kênh trước.')
        session = self.session_id
        session.invalidate_recordset()
        target = self._recording_target()
        target.invalidate_recordset()
        if session.state == 'cancel' or target.youtube_url:
            raise TransferError('Buổi học đã hủy hoặc đã có link YouTube. Hãy kiểm tra trước khi tiếp tục.')
        if parse_drive_url(target.google_drive_url)[0] != self.file_id:
            raise TransferError('Link Drive của buổi học đã thay đổi.')
        return c

    def _drive_headers(self):
        return {'X-Goog-Drive-Resource-Keys': '%s/%s' % (self.file_id, self.resource_key)} if self.resource_key else {}

    def _metadata(self, c):
        self._refresh_upload_title()
        with self._request('drive', 'GET', 'https://www.googleapis.com/drive/v3/files/' + self.file_id,
                params={'fields': 'size,mimeType,md5Checksum,capabilities(canDownload)', 'supportsAllDrives': 'true'},
                headers=self._drive_headers()) as response:
            info = response.json()
        size = int(info.get('size', 0))
        if not info.get('capabilities', {}).get('canDownload'):
            raise TransferError('Tài khoản Drive không có quyền tải video này.')
        if not info.get('mimeType', '').startswith('video/'):
            raise TransferError('File Drive không phải video được hỗ trợ.')
        if not info.get('md5Checksum'):
            raise TransferError('File chưa sẵn sàng hoặc không có checksum để kiểm tra toàn vẹn.')
        if size <= 0 or size > c.max_file_gb * 1024 ** 3:
            raise TransferError('Video rỗng hoặc vượt dung lượng tối đa đã cấu hình.')
        path = self._path()
        cached = path.stat().st_size if path.exists() else 0
        if shutil.disk_usage(path.parent).free < max(0, size - cached) + 512 * 1024 ** 2:
            raise TransferError('Máy chủ không đủ dung lượng trống để tải video.')
        self.write({'total_bytes': size, 'mime_type': info['mimeType'],
                    'checksum': info['md5Checksum'], 'state': 'downloading',
                    'cache_started_at': self.cache_started_at or fields.Datetime.now()})

    def _download(self):
        path = self._path()
        start = path.stat().st_size if path.exists() else 0
        total = int(self.total_bytes)
        if start < total:
            end = min(start + CHUNK, total) - 1
            headers = self._drive_headers()
            headers['Range'] = 'bytes=%s-%s' % (start, end)
            with self._request('drive', 'GET', 'https://www.googleapis.com/drive/v3/files/' + self.file_id,
                    params={'alt': 'media', 'supportsAllDrives': 'true'}, headers=headers, stream=True) as response:
                if response.status_code == 206:
                    if response.headers.get('Content-Range') != 'bytes %s-%s/%s' % (start, end, total):
                        raise TransferError('Drive trả về khoảng dữ liệu không khớp; chưa ghi vào file.')
                elif start != 0 or end != total - 1:
                    raise TransferError('Drive không hỗ trợ tải theo phần cho file này.')
                # Stage the bounded response in memory; partial network reads never corrupt the local file.
                parts, count = [], 0
                for part in response.iter_content(256 * 1024):
                    count += len(part)
                    if count > end - start + 1:
                        raise TransferError('Drive trả về quá số byte yêu cầu.')
                    parts.append(part)
                if count != end - start + 1:
                    raise TransferError('Tải Drive bị gián đoạn.', retry=True)
                with path.open('ab') as output:
                    output.write(b''.join(parts))
                    output.flush()
                    os.fsync(output.fileno())
            start += count
        if start > total:
            raise TransferError('File tạm có dung lượng sai. Hủy yêu cầu và kiểm tra lại nguồn.')
        if start == total:
            digest = hashlib.md5()
            with path.open('rb') as video:
                for part in iter(lambda: video.read(CHUNK), b''):
                    digest.update(part)
            if digest.hexdigest() != self.checksum:
                self._cleanup()
                raise TransferError('Video Drive đã thay đổi hoặc tải lỗi checksum. Kiểm tra nguồn rồi thử lại.')
            self.write({'state': 'uploading'})

    def _start_upload(self, c):
        # Also refresh older queued jobs and account for a second part added after enqueue.
        self._refresh_upload_title()
        with self._request('youtube', 'GET', 'https://www.googleapis.com/youtube/v3/channels',
                params={'part': 'snippet', 'mine': 'true'}) as response:
            items = response.json().get('items', [])
        if len(items) != 1 or items[0]['id'] != c.channel_id:
            raise TransferError('Quyền Google hiện tại không thuộc kênh đã xác nhận. Hãy kết nối lại YouTube.')
        # No content is uploaded by this POST. Persist the returned session BEFORE sending any video bytes.
        with self._request('youtube', 'POST', 'https://www.googleapis.com/upload/youtube/v3/videos',
                params={'uploadType': 'resumable', 'part': 'snippet,status', 'notifySubscribers': 'false'},
                json={'snippet': {'title': self.title, 'categoryId': '27',
                                   'description': self.description},
                      'status': {'privacyStatus': c.privacy, 'selfDeclaredMadeForKids': False}},
                headers={'X-Upload-Content-Length': str(int(self.total_bytes)),
                         'X-Upload-Content-Type': self.mime_type}, allow_redirects=False) as response:
            url = response.headers.get('Location', '')
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'www.googleapis.com' or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise TransferError('Google trả về địa chỉ upload không hợp lệ.')
        self.write({'upload_url': url, 'channel_id': c.channel_id})
        self._checkpoint()

    def _upload(self, c):
        if not self.upload_url:
            self._start_upload(c)
        total = int(self.total_bytes)
        # Query the server after every interruption; do not trust the locally saved offset.
        with self._request('youtube', 'PUT', self.upload_url, data=b'',
                headers={'Content-Length': '0', 'Content-Range': 'bytes */%s' % total},
                allow_redirects=False) as response:
            if response.status_code in (200, 201):
                self._complete(response.json())
                return
            offset = self._offset(response, total)
        path = self._path()
        if not path.exists() or path.stat().st_size != total:
            raise TransferError('Thiếu file tạm để tiếp tục upload. Kiểm tra kết quả trên YouTube trước.', uncertain=True)
        with path.open('rb') as source:
            source.seek(offset)
            data = source.read(CHUNK)
        if not data:
            raise TransferError('Google đã nhận đủ byte nhưng chưa trả kết quả. Kiểm tra lại ở lần tiếp theo.', retry=True)
        with self._request('youtube', 'PUT', self.upload_url, data=data,
                headers={'Content-Type': self.mime_type,
                         'Content-Range': 'bytes %s-%s/%s' % (offset, offset + len(data) - 1, total)},
                allow_redirects=False) as response:
            if response.status_code in (200, 201):
                self._complete(response.json())
            else:
                self.write({'uploaded_bytes': self._offset(response, total)})

    def _offset(self, response, total):
        value = response.headers.get('Range', '')
        match = re.fullmatch(r'bytes=0-(\d+)', value) if value else None
        if value and not match:
            raise TransferError('YouTube trả về tiến độ không hợp lệ.', uncertain=True)
        offset = int(match.group(1)) + 1 if match else 0
        if offset > total:
            raise TransferError('Tiến độ YouTube vượt dung lượng video.', uncertain=True)
        return offset

    def _complete(self, info):
        video_id = info.get('id', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            raise TransferError('YouTube chưa trả về ID video hợp lệ. Cần kiểm tra trên kênh.', uncertain=True)
        url = 'https://youtu.be/' + video_id
        session = self.session_id
        session.invalidate_recordset()
        message = False
        target = self._recording_target()
        target.invalidate_recordset()
        if not target.youtube_url and target.google_drive_url == self.source_url:
            # Updating the video link only must also work after the payroll period was locked.
            target.sudo().with_context(edu_payroll_internal=True).write({'youtube_url': url})
        else:
            message = 'Video đã tải lên. Link buổi học đã thay đổi nên không ghi đè; dùng link trong lịch sử này.'
        self.write({'state': 'done', 'video_url': url, 'uploaded_bytes': self.total_bytes,
                    'finished_at': fields.Datetime.now(), 'error': message, 'upload_url': False})
        self._checkpoint()
        self._cleanup()

    def _step(self):
        c = self._guard()
        if self.state == 'queued':
            self._metadata(c)
        elif self.state == 'downloading':
            self._download()
        elif self.state == 'uploading':
            self._upload(c)

    @api.model
    def _cron_process(self):
        c = self.env.ref('edu_video.config_default').sudo()
        if not c.processing_enabled:
            return
        job = self.sudo().search([('state', 'in', ACTIVE), '|', ('next_attempt', '=', False),
                                 ('next_attempt', '<=', fields.Datetime.now())], order='id', limit=1)
        if not job:
            return
        self.env.cr.execute('SELECT pg_try_advisory_lock(%s, %s)', [LOCK_NAMESPACE, job.id])
        if not self.env.cr.fetchone()[0]:
            return
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and job.state in ACTIVE:
                c.invalidate_recordset()
                if not c.processing_enabled:
                    break
                try:
                    job._step()
                    job.write({'attempts': 0, 'next_attempt': False, 'error': False if job.state != 'done' else job.error})
                    job._checkpoint()
                except (requests.RequestException, TransferError, UserError, ValueError, OSError) as exc:
                    retry = isinstance(exc, requests.RequestException) or (isinstance(exc, TransferError) and exc.retry)
                    uncertain = isinstance(exc, TransferError) and exc.uncertain
                    attempts = job.attempts + 1
                    message = str(exc) if isinstance(exc, (TransferError, UserError)) else 'Lỗi kết nối, dữ liệu hoặc lưu file tạm. Có thể thử lại; phiên upload hiện tại được giữ.'
                    job.write({'state': 'uncertain' if uncertain else (job.state if retry and attempts <= 3 else 'failed'),
                        'attempts': attempts, 'error': message,
                        'next_attempt': fields.Datetime.now() + timedelta(minutes=min(2 ** attempts, 30))})
                    job._checkpoint()
                    break
        except Exception:
            self.env.cr.rollback()
            raise
        finally:
            self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', [LOCK_NAMESPACE, job.id])

    def _action_lock(self):
        if not self.env.user.has_group('edu_gvnn.group_edu_manager'):
            raise UserError('Chỉ quản lý GVNN được thay đổi yêu cầu video.')
        self.ensure_one()
        self.check_access_rights('read')
        self.check_access_rule('read')
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', [LOCK_NAMESPACE, self.id])
        if not self.env.cr.fetchone()[0]:
            raise UserError('Video đang xử lý một phần dữ liệu. Hãy thử lại sau khoảng một phút.')
        self.invalidate_recordset()

    def action_retry(self):
        self._action_lock()
        if self.state != 'failed' and not (self.state == 'cancelled' and not self.upload_url):
            raise UserError('Chỉ thử lại yêu cầu lỗi hoặc đã hủy trước upload. Trạng thái chưa rõ cần kiểm tra trên YouTube.')
        vals = {'state': 'uploading' if self.upload_url else 'queued',
                'error': False, 'attempts': 0, 'next_attempt': False}
        if self._cache_is_expired():
            self._cleanup()
            if self._path().exists():
                raise UserError('Chưa dọn được file tạm quá hạn. Kiểm tra quyền ghi ổ đĩa trước khi thử lại.')
            vals.update(cache_started_at=False, cache_expired=False, uploaded_bytes=0,
                        total_bytes=0, checksum=False, mime_type=False)
        self.sudo().write(vals)
        return True

    def action_cancel(self):
        self._action_lock()
        if self.state == 'done':
            raise UserError('Video đã tải lên; không thể hủy yêu cầu đã hoàn tất.')
        self.sudo().write({'state': 'cancelled', 'error': 'Đã dừng tại Odoo. Không xóa video đã nhận trên YouTube; cần kiểm tra kênh nếu upload đã bắt đầu.'})
        self._cleanup()
        return True

    def action_restart_checked(self):
        self._action_lock()
        if self.state not in ('uncertain', 'cancelled', 'failed'):
            raise UserError('Chỉ tạo phiên mới sau khi yêu cầu cũ đã dừng và bạn kiểm tra kênh YouTube.')
        if self._recording_target().youtube_url:
            raise UserError('Buổi học đã có link YouTube; không tạo thêm bản upload.')
        self._cleanup()
        if self._cache_is_expired() and self._path().exists():
            raise UserError('Chưa dọn được file tạm quá hạn. Kiểm tra quyền ghi ổ đĩa trước khi tạo phiên mới.')
        self.sudo().write({'state': 'queued', 'upload_url': False, 'channel_id': False,
            'cache_started_at': False, 'cache_expired': False,
            'uploaded_bytes': 0, 'total_bytes': 0, 'checksum': False, 'mime_type': False,
            'attempts': 0, 'next_attempt': False,
            'error': 'Quản lý đã xác nhận kiểm tra trên YouTube và yêu cầu tạo phiên upload mới.'})
        return True
