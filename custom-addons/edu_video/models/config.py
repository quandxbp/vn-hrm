import base64
import json
import secrets
import time
from urllib.parse import urlencode, urlparse

import requests

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


CALLBACK = 'http://localhost:8069/edu-video/google/callback'
DRIVE_SCOPES = 'https://www.googleapis.com/auth/drive.readonly'
YOUTUBE_SCOPES = ' '.join([
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly',
])
SCOPES = DRIVE_SCOPES + ' ' + YOUTUBE_SCOPES


class GoogleVideoConfig(models.Model):
    _name = 'edu.video.config'
    _description = 'Kết nối Google Video'

    name = fields.Char(default='Google Drive → YouTube', required=True)
    client_id = fields.Char('Client ID', copy=False)
    client_secret = fields.Char('Client Secret', copy=False, groups='base.group_no_one')
    credential_json = fields.Binary('File JSON OAuth', attachment=False, copy=False)
    credential_filename = fields.Char('Tên file')
    redirect_uri = fields.Char('Redirect URI', default=CALLBACK, required=True,
        help='Địa chỉ HTTPS của Odoo + /edu-video/google/callback. Phải trùng Google Cloud.')
    auto_upload = fields.Boolean('Tự xếp hàng khi nhập link Drive', default=False)
    processing_enabled = fields.Boolean('Cho phép xử lý video nền', default=False)
    max_file_gb = fields.Integer('Dung lượng video tối đa (GB)', default=10, required=True)

    @api.constrains('redirect_uri', 'max_file_gb')
    def _validate_settings(self):
        for rec in self:
            uri = urlparse(rec.redirect_uri or '')
            if (uri.path != '/edu-video/google/callback' or uri.query or uri.fragment
                    or uri.username or uri.password or not uri.hostname
                    or (uri.scheme != 'https' and not (uri.scheme == 'http' and uri.hostname in ('localhost', '127.0.0.1')))):
                raise ValidationError('Callback phải là HTTPS + /edu-video/google/callback (localhost có thể dùng HTTP).')
            if not 1 <= rec.max_file_gb <= 256:
                raise ValidationError('Dung lượng giới hạn phải từ 1 đến 256 GB.')

    @api.constrains('processing_enabled')
    def _validate_processing(self):
        for rec in self.filtered('processing_enabled'):
            rec._ready()
    state = fields.Selection([('disconnected', 'Chưa kết nối'), ('connected', 'Đã kết nối')],
                             default='disconnected', readonly=True)
    channel_name = fields.Char('Kênh YouTube', readonly=True)
    channel_id = fields.Char('Channel ID', readonly=True)
    channel_handle = fields.Char('Handle YouTube', readonly=True)
    expected_channel_handle = fields.Char('Kênh YouTube cần kết nối',
        help='Ví dụ @YUYONG90. Kết nối sẽ bị từ chối nếu Google trả về kênh khác.')
    drive_state = fields.Selection([('disconnected', 'Chưa kết nối'), ('connected', 'Đã kết nối')],
                                   default='disconnected', readonly=True)
    privacy = fields.Selection([('unlisted', 'Không công khai')], default='unlisted', readonly=True)
    refresh_token = fields.Char(copy=False, groups='base.group_no_one')
    access_token = fields.Char(copy=False, groups='base.group_no_one')
    expires_at = fields.Float(copy=False, groups='base.group_no_one')
    youtube_refresh_token = fields.Char(copy=False, groups='base.group_no_one')
    youtube_access_token = fields.Char(copy=False, groups='base.group_no_one')
    youtube_expires_at = fields.Float(copy=False, groups='base.group_no_one')

    def _admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError('Chỉ quản trị viên được cấu hình kết nối Google.')
        self.ensure_one()

    def _import_credentials(self, raw):
        self._admin()
        try:
            data = json.loads(raw)
            web = data['web']
            client_id, secret = web['client_id'], web['client_secret']
            if not isinstance(client_id, str) or not isinstance(secret, str) or not secret:
                raise ValueError()
            if self.redirect_uri not in web.get('redirect_uris', []):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise UserError('Cần file JSON loại Web application với đúng Redirect URI: ' + self.redirect_uri)
        self.sudo().write({
            'client_id': client_id, 'client_secret': secret,
            'credential_json': False, 'credential_filename': False,
            'refresh_token': False, 'access_token': False, 'expires_at': 0,
            'youtube_refresh_token': False, 'youtube_access_token': False, 'youtube_expires_at': 0,
            'state': 'disconnected', 'drive_state': 'disconnected',
            'channel_name': False, 'channel_id': False, 'channel_handle': False,
            'processing_enabled': False,
        })

    def action_import(self):
        self._admin()
        if not self.credential_json:
            raise UserError('Hãy chọn file JSON OAuth trước.')
        self._import_credentials(base64.b64decode(self.credential_json))
        return True

    def action_connect(self):
        return self._connect('youtube')

    def action_connect_drive(self):
        return self._connect('drive')

    def _connect(self, service):
        self._admin()
        from odoo.http import request
        config = self.sudo()
        if not config.client_id or not config.client_secret:
            raise UserError('Hãy nhập file JSON OAuth trước.')
        nonce = secrets.token_urlsafe(32)
        request.session['edu_video_oauth'] = {
            'state': nonce, 'config': self.id, 'uid': self.env.uid,
            'db': self.env.cr.dbname, 'expires': time.time() + 600,
            'service': service,
            'redirect_uri': config.redirect_uri,
        }
        return {'type': 'ir.actions.act_url', 'target': 'self', 'url':
                'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
                    'client_id': config.client_id, 'redirect_uri': config.redirect_uri,
                    'response_type': 'code',
                    'scope': DRIVE_SCOPES if service == 'drive' else YOUTUBE_SCOPES,
                    'access_type': 'offline', 'prompt': 'select_account consent', 'state': nonce,
                })}

    def _exchange(self, code, service='youtube', redirect_uri=None):
        config = self.sudo()
        try:
            response = requests.post('https://oauth2.googleapis.com/token', data={
                'code': code, 'client_id': config.client_id,
                'client_secret': config.client_secret, 'redirect_uri': redirect_uri or config.redirect_uri,
                'grant_type': 'authorization_code',
            }, timeout=30)
            if response.status_code != 200:
                raise ValueError()
            token = response.json()
            if not token.get('refresh_token') or not token.get('access_token'):
                raise ValueError()
            granted = set(token.get('scope', '').split())
            scopes = DRIVE_SCOPES if service == 'drive' else YOUTUBE_SCOPES
            if not set(scopes.split()).issubset(granted):
                raise ValueError()
            if service == 'drive':
                config.write({
                    'refresh_token': token['refresh_token'], 'access_token': token['access_token'],
                    'expires_at': time.time() + int(token.get('expires_in', 3600)),
                    'drive_state': 'connected',
                })
                return
            channel = requests.get('https://www.googleapis.com/youtube/v3/channels',
                params={'part': 'snippet', 'mine': 'true'},
                headers={'Authorization': 'Bearer ' + token['access_token']}, timeout=30)
            if channel.status_code != 200:
                raise ValueError()
            items = channel.json().get('items', [])
            if len(items) != 1:
                raise UserError('Không xác định được một kênh YouTube. Hãy chọn lại tài khoản/kênh.')
            handle = items[0]['snippet'].get('customUrl', '')
            expected = (config.expected_channel_handle or '').strip().lstrip('@').casefold()
            if expected and handle.strip().lstrip('@').casefold() != expected:
                raise UserError('Google đang cấp quyền cho kênh %s (%s), không phải @%s. '
                                'Hãy kết nối lại và chọn đúng kênh YouTube.' % (
                                    items[0]['snippet']['title'], handle or 'không có handle', expected))
        except (requests.RequestException, ValueError, KeyError, TypeError):
            raise UserError('Kết nối Google chưa hoàn tất. Hãy thử lại và cấp đủ quyền Drive/YouTube.')
        config.write({
            'youtube_refresh_token': token['refresh_token'], 'youtube_access_token': token['access_token'],
            'youtube_expires_at': time.time() + int(token.get('expires_in', 3600)),
            'channel_id': items[0]['id'], 'channel_name': items[0]['snippet']['title'],
            'channel_handle': handle, 'state': 'connected',
        })

    def action_disconnect(self):
        self._admin()
        self.sudo().write({'refresh_token': False, 'access_token': False,
                           'expires_at': 0, 'state': 'disconnected',
                           'drive_state': 'disconnected',
                           'youtube_refresh_token': False, 'youtube_access_token': False,
                           'youtube_expires_at': 0,
                           'processing_enabled': False,
                           'channel_id': False, 'channel_name': False, 'channel_handle': False})
        return True

    def _ready(self):
        self.ensure_one()
        c = self.sudo()
        if c.drive_state != 'connected' or c.state != 'connected' or not c.channel_id:
            raise UserError('Cần kết nối Google Drive và đúng kênh YouTube trước.')
        expected = (c.expected_channel_handle or '').strip().lstrip('@').casefold()
        if expected and (c.channel_handle or '').lstrip('@').casefold() != expected:
            raise UserError('Kênh YouTube hiện tại không khớp kênh cần kết nối.')
        if not c.refresh_token or not c.youtube_refresh_token:
            raise UserError('Thiếu quyền truy cập nền. Hãy kết nối lại Google.')

    def _token(self, service, force=False):
        c = self.sudo()
        prefix = 'youtube_' if service == 'youtube' else ''
        if not force and c[prefix + 'access_token'] and c[prefix + 'expires_at'] > time.time() + 120:
            return c[prefix + 'access_token']
        if not c[prefix + 'refresh_token']:
            raise UserError('Cần kết nối lại %s.' % service)
        try:
            response = requests.post('https://oauth2.googleapis.com/token', data={
                'client_id': c.client_id, 'client_secret': c.client_secret,
                'refresh_token': c[prefix + 'refresh_token'], 'grant_type': 'refresh_token',
            }, timeout=30)
            if response.status_code != 200:
                raise UserError('Không làm mới được quyền %s (HTTP %s). Hãy kiểm tra hoặc kết nối lại Google.' % (service, response.status_code))
            token = response.json()
            c.write({prefix + 'access_token': token['access_token'],
                     prefix + 'expires_at': time.time() + int(token.get('expires_in', 3600))})
            return token['access_token']
        except (ValueError, KeyError, TypeError):
            raise UserError('Google trả về dữ liệu quyền không hợp lệ. Hãy kết nối lại.')
