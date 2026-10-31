import base64
import hashlib
import io
import re
from datetime import timedelta
from functools import lru_cache

import requests
from PIL import Image, ImageDraw, ImageFont

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_resource

from .job import LOCK_NAMESPACE, TransferError


@lru_cache(maxsize=64)
def _font(size, bold=False):
    candidates = (['DejaVuSans-Bold.ttf', 'arialbd.ttf'] if bold else
                  ['DejaVuSans.ttf', 'arial.ttf'])
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    raise UserError('Thiếu font DejaVu Sans hoặc Arial trên máy xử lý video.')


def _draw_fitted_text(draw, text, position, width, max_size, min_size, fill, max_lines=2):
    """Fit names in a bounded region at native resolution, with a safe overflow marker."""
    text = ' '.join(text.split())
    if len(text) > 500:
        text = text[:500].rstrip() + '…'
    for size in range(max_size, min_size - 1, -4):
        lines, line = [], ''
        for word in text.split():
            candidate = (line + ' ' + word).strip()
            if draw.textbbox((0, 0), candidate, font=_font(size, True))[2] > width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        if len(lines) <= max_lines and all(draw.textbbox((0, 0), value, font=_font(size, True))[2] <= width for value in lines):
            break
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] += '…'
    for index, line in enumerate(lines):
        while line and draw.textbbox((0, 0), line, font=_font(size, True))[2] > width:
            line = line[:-2].rstrip() + '…' if len(line) > 2 else '…'
        draw.text((position[0], position[1] + index * (size + 24)), line,
                  font=_font(size, True), fill=fill)


def render_thumbnail(teacher, week, lesson_date, part=None, students=None):
    """Render text at native 4K resolution; never upscale an old thumbnail."""
    image = Image.new('RGB', (3840, 2160), '#f7fafc')
    draw = ImageDraw.Draw(image)
    draw.rectangle((2550, 0, 3840, 2160), fill='#123e63')
    draw.ellipse((3050, -550, 4550, 950), outline='#1e5278', width=80)
    draw.ellipse((2670, 1450, 4170, 2950), outline='#1e5278', width=80)
    draw.rectangle((0, 0, 2550, 24), fill='#19adab')
    logo_path = get_module_resource('vnpt_base', 'static', 'src', 'img', 'kim-academy-logo.png')
    if logo_path:
        draw.rounded_rectangle((160, 115, 440, 395), radius=40, fill='white')
        with Image.open(logo_path) as logo:
            logo = logo.convert('RGBA')
            bounds = logo.getchannel('A').getbbox()
            if bounds:
                logo = logo.crop(bounds)
                logo.thumbnail((230, 230), getattr(Image, 'Resampling', Image).LANCZOS)
                image.paste(logo, (300 - logo.width // 2, 255 - logo.height // 2), logo)
    draw.text((500, 160), 'KIM ACADEMY', font=_font(100, True), fill='#123e63')
    draw.text((505, 290), 'ENGLISH LEARNING', font=_font(48), fill='#607d91')
    draw.rounded_rectangle((200, 530, 1390, 675), radius=34, fill='#e0f1ee')
    draw.text((245, 555), 'BUỔI HỌC TIẾNG ANH', font=_font(76, True), fill='#1a746f')
    _draw_fitted_text(draw, teacher or 'GIÁO VIÊN', (200, 770), 2100, 220, 72, '#123e63')
    if students:
        draw.rectangle((210, 1300, 440, 1315), fill='#19adab')
        draw.text((200, 1380), 'HỌC VIÊN', font=_font(58, True), fill='#607d91')
        _draw_fitted_text(draw, ' & '.join(students), (200, 1480), 2100, 120, 64, '#1a746f')
    draw.text((200, 1850), lesson_date, font=_font(110, True), fill='#123e63')
    draw.text((200, 2030), 'kimacademy.uk', font=_font(48), fill='#58768c')
    draw.text((2760, 505), 'TUẦN HỌC', font=_font(84, True), fill='#a9dbe1')
    week_text = str(week)
    week_size = 570
    while week_size > 100 and draw.textbbox((0, 0), week_text, font=_font(week_size, True))[2] > 930:
        week_size -= 10
    draw.text((2750, 790), week_text, font=_font(week_size, True), fill='white')
    if part is not None:
        draw.rounded_rectangle((2750, 1580, 3650, 1780), radius=42, fill='#19adab')
        draw.text((2810, 1620), 'PHẦN %s' % part, font=_font(100, True), fill='white')
    for quality in (95, 92, 88):
        output = io.BytesIO()
        image.save(output, 'JPEG', quality=quality, subsampling=0, optimize=True)
        if output.tell() < 2 * 1024 ** 2:
            return output.getvalue()
    raise UserError('Ảnh bìa vượt giới hạn dung lượng. Hãy kiểm tra mẫu ảnh trước khi thử lại.')


class EduVideoOptimization(models.Model):
    _inherit = 'edu.video.job'

    optimization_state = fields.Selection([
        ('skipped', 'Không xếp hàng'), ('pending', 'Chờ ảnh bìa / playlist'),
        ('done', 'Hoàn tất'), ('failed', 'Cần xử lý')],
        string='Ảnh bìa / Playlist', default='skipped', readonly=True, copy=False)
    optimization_error = fields.Text('Lỗi ảnh bìa / playlist', readonly=True, copy=False)
    optimization_attempts = fields.Integer('Số lần xử lý ảnh bìa / playlist', readonly=True, copy=False)
    optimization_next_attempt = fields.Datetime('Lần thử lại tiếp theo', readonly=True, copy=False)
    optimization_teacher_id = fields.Many2one('edu.teacher', readonly=True, copy=False, ondelete='restrict')
    thumbnail_image = fields.Binary('Ảnh bìa tự tạo', attachment=True, readonly=True, copy=False)
    thumbnail_applied = fields.Boolean('Đã đặt ảnh bìa', readonly=True, copy=False)
    playlist_id = fields.Char('YouTube Playlist ID', readonly=True, copy=False)
    playlist_title = fields.Char('Tên playlist', readonly=True, copy=False)
    playlist_item_id = fields.Char('YouTube Playlist Item ID', readonly=True, copy=False)
    playlist_create_pending = fields.Boolean(readonly=True, copy=False)
    playlist_url = fields.Char('Playlist YouTube', compute='_compute_playlist_url')

    @api.depends('playlist_id')
    def _compute_playlist_url(self):
        for job in self:
            job.playlist_url = ('https://www.youtube.com/playlist?list=' + job.playlist_id
                                if job.playlist_id else False)

    def _generated_thumbnail(self):
        self.ensure_one()
        if not self.thumbnail_image:
            teacher = self.optimization_teacher_id or self.session_id.teacher_id
            label = ' '.join(filter(None, [
                {'mr': 'MR', 'ms': 'MS'}.get(teacher.teaching_title), teacher.name.upper()]))
            parts = self.session_id._recording_parts()
            image = render_thumbnail(label, self.session_id.week_id.number or '?',
                                     self.session_id.date.strftime('%d/%m/%Y'),
                                     self.part_number if sum(bool(p['drive'] or p['youtube']) for p in parts) > 1 else None,
                                     students=self._youtube_student_names(self.session_id))
            self.thumbnail_image = base64.b64encode(image)
            self._checkpoint()
        return base64.b64decode(self.thumbnail_image)

    def _playlist_description(self):
        return 'Các buổi học tiếng Anh trực tuyến tại Kim Academy.\n' + self._playlist_title()

    def _playlist_title(self):
        teacher = self.optimization_teacher_id
        label = ' '.join(filter(None, [
            {'mr': 'MR', 'ms': 'MS'}.get(teacher.teaching_title), teacher.name.upper()]))
        return self.playlist_title or ('KIMENGLISH - %s' % label)

    def _find_or_create_playlist(self, config):
        if self.playlist_id:
            return self.playlist_id
        teacher = self.optimization_teacher_id
        previous = self.search([('channel_id', '=', self.channel_id),
                                ('optimization_teacher_id', '=', teacher.id),
                                ('playlist_id', '!=', False)], order='id desc', limit=1)
        if previous:
            self.write({'playlist_id': previous.playlist_id, 'playlist_title': previous.playlist_title,
                        'playlist_create_pending': False})
            self._checkpoint()
            return self.playlist_id
        unresolved_job = self.search([('channel_id', '=', self.channel_id),
                                      ('optimization_teacher_id', '=', teacher.id),
                                      ('playlist_create_pending', '=', True)], limit=1)
        title = self.playlist_title or unresolved_job.playlist_title or self._playlist_title()
        if len(title) > 150 or '<' in title or '>' in title:
            raise UserError('Tên giáo viên quá dài hoặc chứa ký tự không hợp lệ để tạo playlist.')
        self.playlist_title = title
        self._checkpoint()
        description = self._playlist_description()
        token = None
        seen = set()
        while True:
            params = {'part': 'snippet', 'mine': 'true', 'maxResults': 50}
            if token:
                params['pageToken'] = token
            with self._request('youtube', 'GET', 'https://www.googleapis.com/youtube/v3/playlists',
                               params=params) as response:
                page = response.json()
            for item in page.get('items', []):
                if (item['snippet'].get('channelId') == self.channel_id and
                        item['snippet'].get('title') == title):
                    self.write({'playlist_id': item['id'], 'playlist_create_pending': False})
                    self._checkpoint()
                    return self.playlist_id
            token = page.get('nextPageToken')
            if not token:
                break
            if token in seen:
                raise UserError('YouTube trả về trang playlist lặp. Hãy thử lại sau.')
            seen.add(token)
        unresolved = self.search_count([
            ('channel_id', '=', self.channel_id),
            ('optimization_teacher_id', '=', teacher.id), ('playlist_create_pending', '=', True)])
        if unresolved:
            raise UserError('Lần tạo playlist trước chưa rõ kết quả. Kiểm tra playlist trên YouTube trước khi thử lại.')
        self.playlist_create_pending = True
        self._checkpoint()
        with self._request('youtube', 'POST', 'https://www.googleapis.com/youtube/v3/playlists',
                params={'part': 'snippet,status'}, json={
                    'snippet': {'title': title, 'description': description},
                    'status': {'privacyStatus': config.privacy}}) as response:
            playlist_id = response.json().get('id', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,100}', playlist_id):
            raise UserError('YouTube chưa trả ID playlist hợp lệ. Kiểm tra playlist trước khi thử lại.')
        self.write({'playlist_id': playlist_id, 'playlist_create_pending': False})
        self._checkpoint()
        return playlist_id

    def _playlist_items(self, playlist_id, video_id):
        with self._request('youtube', 'GET', 'https://www.googleapis.com/youtube/v3/playlistItems',
                           params={'part': 'snippet', 'playlistId': playlist_id, 'videoId': video_id,
                                   'maxResults': 50}) as response:
            return response.json().get('items', [])

    def _add_to_playlist(self, config, video_id):
        playlist_id = self._find_or_create_playlist(config)
        existing = self._playlist_items(playlist_id, video_id)
        if existing:
            self.playlist_item_id = existing[0]['id']
            self._checkpoint()
            return
        snippet = {'playlistId': playlist_id, 'resourceId': {'kind': 'youtube#video', 'videoId': video_id}}
        # Keep parts of the same lesson adjacent, even if part 2 finishes first.
        siblings = self.search([('session_id', '=', self.session_id.id), ('id', '!=', self.id),
                                ('channel_id', '=', self.channel_id), ('playlist_id', '=', playlist_id),
                                ('playlist_item_id', '!=', False)], order='id')
        lower = siblings.filtered(lambda j: j.part_number < self.part_number).sorted('part_number', reverse=True)
        higher = siblings.filtered(lambda j: j.part_number > self.part_number).sorted('part_number')
        for sibling in lower | higher:
            items = self._playlist_items(playlist_id, sibling.video_url.rsplit('/', 1)[-1])
            if items:
                snippet['position'] = items[0]['snippet']['position'] + (sibling.part_number < self.part_number)
                break
        with self._request('youtube', 'POST', 'https://www.googleapis.com/youtube/v3/playlistItems',
                           params={'part': 'snippet'}, json={'snippet': snippet}) as response:
            item_id = response.json().get('id')
        if not item_id:
            raise UserError('YouTube chưa xác nhận thêm video vào playlist. Hãy thử lại để kiểm tra kết quả.')
        self.playlist_item_id = item_id
        self._checkpoint()

    def _optimize_uploaded_video(self, config):
        self.ensure_one()
        if self.state != 'done' or self.channel_id != config.channel_id:
            raise UserError('Chỉ tối ưu video đã upload lên đúng kênh đang kết nối.')
        video_id = self.video_url.rsplit('/', 1)[-1]
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            raise UserError('Video ID không hợp lệ.')
        self.optimization_attempts += 1
        with self._request('youtube', 'GET', 'https://www.googleapis.com/youtube/v3/channels',
                           params={'part': 'snippet', 'mine': 'true'}) as response:
            channels = response.json().get('items', [])
        if len(channels) != 1 or channels[0]['id'] != self.channel_id:
            raise UserError('Quyền Google không thuộc kênh đã upload video. Hãy kết nối lại đúng kênh.')
        errors, retryable = [], []
        if config.auto_thumbnail and not self.thumbnail_applied:
            try:
                with self._request('youtube', 'POST', 'https://www.googleapis.com/upload/youtube/v3/thumbnails/set',
                        params={'videoId': video_id, 'uploadType': 'media'},
                        data=self._generated_thumbnail(), headers={'Content-Type': 'image/jpeg'}):
                    pass
                self.thumbnail_applied = True
                self._checkpoint()
            except (requests.RequestException, TransferError, UserError, ValueError, OSError) as exc:
                retryable.append(self._optimization_retryable(exc))
                errors.append('Ảnh bìa: ' + (str(exc) if isinstance(exc, (TransferError, UserError)) else
                              'Không gửi được ảnh bìa. Kiểm tra kết nối rồi thử lại.'))
        if config.auto_playlist and not self.playlist_item_id:
            try:
                if not config.playlist_authorized:
                    raise UserError('Cần kết nối lại YouTube và cấp thêm quyền quản lý playlist.')
                self._add_to_playlist(config, video_id)
            except (requests.RequestException, TransferError, UserError, ValueError, KeyError) as exc:
                retryable.append(self._optimization_retryable(exc))
                errors.append('Playlist: ' + (str(exc) if isinstance(exc, (TransferError, UserError)) else
                              'Chưa xác nhận kết quả trên YouTube. Kiểm tra playlist rồi thử lại.'))
        self._optimization_result(errors, any(retryable))

    def _optimization_retryable(self, exc):
        # Newly uploaded videos/playlists may briefly be unavailable to the next API call.
        return isinstance(exc, requests.RequestException) or isinstance(exc, TransferError) and (
            exc.retry or exc.status == 404)

    def _optimization_result(self, errors, retryable=False):
        retry = bool(errors and retryable and self.optimization_attempts < 4)
        self.write({'optimization_state': 'pending' if retry else 'failed' if errors else 'done',
                    'optimization_error': '\n'.join(errors) or False,
                    'optimization_next_attempt': fields.Datetime.now() + timedelta(
                        minutes=2 ** self.optimization_attempts) if retry else False})

    def _cron_optimize(self):
        config = self.env.ref('edu_video.config_default').sudo()
        if not config.processing_enabled:
            return
        job = self.sudo().search([('state', '=', 'done'), ('optimization_state', '=', 'pending'),
                                '|', ('optimization_next_attempt', '=', False),
                                ('optimization_next_attempt', '<=', fields.Datetime.now())],
                                order='id', limit=1)
        if not job:
            return
        # One channel at a time prevents concurrent playlist creation/reordering.
        channel_lock = int(hashlib.sha256((config.channel_id or '').encode()).hexdigest()[:7], 16)
        locks = [(LOCK_NAMESPACE, job.id), (87422, channel_lock)]
        held = []
        try:
            for lock in locks:
                self.env.cr.execute('SELECT pg_try_advisory_lock(%s, %s)', lock)
                if not self.env.cr.fetchone()[0]:
                    return
                held.append(lock)
            job.invalidate_recordset()
            if job.optimization_state != 'pending' or job.state != 'done':
                return
            try:
                attempts_before = job.optimization_attempts
                config._ready()
                job._optimize_uploaded_video(config)
            except (requests.RequestException, TransferError, UserError, ValueError) as exc:
                if job.optimization_attempts == attempts_before:
                    job.optimization_attempts += 1
                message = str(exc) if isinstance(exc, (TransferError, UserError)) else 'Không kết nối được YouTube. Kiểm tra kết nối rồi thử lại.'
                job._optimization_result([message], job._optimization_retryable(exc))
            job._checkpoint()
        finally:
            for lock in reversed(held):
                self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', lock)

    def action_retry_optimization(self):
        self._action_lock()
        if self.state != 'done' or self.optimization_state != 'failed':
            raise UserError('Chỉ thử lại ảnh bìa / playlist của video đã upload và đang báo lỗi.')
        self.sudo().write({'optimization_state': 'pending', 'optimization_error': False,
                           'playlist_create_pending': False, 'optimization_attempts': 0,
                           'optimization_next_attempt': False})
        return True
