import base64
import hashlib
import io
import re

import requests
from PIL import Image, ImageDraw, ImageFont

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_resource

from .job import LOCK_NAMESPACE, TransferError


def _font(size, bold=False):
    candidates = (['DejaVuSans-Bold.ttf', 'arialbd.ttf'] if bold else
                  ['DejaVuSans.ttf', 'arial.ttf'])
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    raise UserError('Thiếu font DejaVu Sans hoặc Arial trên máy xử lý video.')


def render_thumbnail(teacher, week, lesson_date, part=None):
    """Create a branded JPEG; never stretch/re-encode the lesson video."""
    image = Image.new('RGB', (1280, 720), '#f4f8fc')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1280, 164), fill='#123e63')
    draw.rectangle((0, 164, 16, 720), fill='#19adab')
    logo_path = get_module_resource('vnpt_base', 'static', 'src', 'img', 'kim-academy-logo.png')
    if logo_path:
        draw.rounded_rectangle((48, 20, 178, 144), radius=12, fill='white')
        with Image.open(logo_path) as logo:
            logo = logo.convert('RGBA')
            logo.thumbnail((112, 112))
            image.paste(logo, (58, 26), logo)
    draw.text((198, 44), 'KIM ACADEMY', font=_font(48, True), fill='white')
    draw.text((200, 103), 'ENGLISH CLASS RECORDING', font=_font(22), fill='#b9e6ec')
    # Fit long teacher names on two lines, including individual long words.
    words = teacher.split()
    lines, line = [], ''
    for word in words:
        candidate = (line + ' ' + word).strip()
        if draw.textbbox((0, 0), candidate, font=_font(58, True))[2] > 1130 and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    text = '\n'.join(lines[:2])
    size = 58
    while size > 18 and draw.multiline_textbbox((0, 0), text, font=_font(size, True))[2] > 1130:
        size -= 2
    if len(lines) > 2:
        text = teacher
        while size > 12 and draw.textbbox((0, 0), text, font=_font(size, True))[2] > 1130:
            size -= 2
    draw.multiline_text((64, 226), text, font=_font(size, True), fill='#123e63', spacing=10)
    label = 'WEEK %s' % week
    if part is not None:
        label += '  |  PART %s' % part
    draw.rounded_rectangle((64, 421, 1216, 506), radius=18, fill='#e0eff7')
    draw.text((90, 436), label, font=_font(40, True), fill='#145b88')
    draw.text((68, 545), lesson_date, font=_font(32), fill='#4a657b')
    draw.line((64, 622, 1216, 622), fill='#ccdde9', width=2)
    draw.text((68, 648), 'kimacademy.uk', font=_font(24), fill='#316985')
    output = io.BytesIO()
    image.save(output, 'JPEG', quality=90, optimize=True)
    return output.getvalue()


class EduVideoOptimization(models.Model):
    _inherit = 'edu.video.job'

    optimization_state = fields.Selection([
        ('skipped', 'Không xếp hàng'), ('pending', 'Chờ ảnh bìa / playlist'),
        ('done', 'Hoàn tất'), ('failed', 'Cần xử lý')],
        string='Ảnh bìa / Playlist', default='skipped', readonly=True, copy=False)
    optimization_error = fields.Text('Lỗi ảnh bìa / playlist', readonly=True, copy=False)
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
                                     self.part_number if sum(bool(p['drive'] or p['youtube']) for p in parts) > 1 else None)
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
        with self._request('youtube', 'GET', 'https://www.googleapis.com/youtube/v3/channels',
                           params={'part': 'snippet', 'mine': 'true'}) as response:
            channels = response.json().get('items', [])
        if len(channels) != 1 or channels[0]['id'] != self.channel_id:
            raise UserError('Quyền Google không thuộc kênh đã upload video. Hãy kết nối lại đúng kênh.')
        errors = []
        if config.auto_thumbnail and not self.thumbnail_applied:
            try:
                with self._request('youtube', 'POST', 'https://www.googleapis.com/upload/youtube/v3/thumbnails/set',
                        params={'videoId': video_id, 'uploadType': 'media'},
                        data=self._generated_thumbnail(), headers={'Content-Type': 'image/jpeg'}):
                    pass
                self.thumbnail_applied = True
                self._checkpoint()
            except (requests.RequestException, TransferError, UserError, ValueError, OSError) as exc:
                errors.append('Ảnh bìa: ' + (str(exc) if isinstance(exc, (TransferError, UserError)) else
                              'Không gửi được ảnh bìa. Kiểm tra kết nối rồi thử lại.'))
        if config.auto_playlist and not self.playlist_item_id:
            try:
                if not config.playlist_authorized:
                    raise UserError('Cần kết nối lại YouTube và cấp thêm quyền quản lý playlist.')
                self._add_to_playlist(config, video_id)
            except (requests.RequestException, TransferError, UserError, ValueError, KeyError) as exc:
                errors.append('Playlist: ' + (str(exc) if isinstance(exc, (TransferError, UserError)) else
                              'Chưa xác nhận kết quả trên YouTube. Kiểm tra playlist rồi thử lại.'))
        self.write({'optimization_state': 'failed' if errors else 'done',
                    'optimization_error': '\n'.join(errors) or False})

    def _cron_optimize(self):
        config = self.env.ref('edu_video.config_default').sudo()
        if not config.processing_enabled:
            return
        job = self.sudo().search([('state', '=', 'done'), ('optimization_state', '=', 'pending')],
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
                config._ready()
                job._optimize_uploaded_video(config)
            except (requests.RequestException, TransferError, UserError, ValueError) as exc:
                job.write({'optimization_state': 'failed', 'optimization_error':
                           str(exc) if isinstance(exc, (TransferError, UserError)) else
                           'Không kết nối được YouTube. Kiểm tra kết nối rồi thử lại.'})
            job._checkpoint()
        finally:
            for lock in reversed(held):
                self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', lock)

    def action_retry_optimization(self):
        self._action_lock()
        if self.state != 'done' or self.optimization_state != 'failed':
            raise UserError('Chỉ thử lại ảnh bìa / playlist của video đã upload và đang báo lỗi.')
        self.sudo().write({'optimization_state': 'pending', 'optimization_error': False,
                           'playlist_create_pending': False})
        return True
