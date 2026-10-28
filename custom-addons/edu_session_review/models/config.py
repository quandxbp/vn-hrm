import re
import requests

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ReviewConfig(models.Model):
    _inherit = 'edu.video.config'

    review_enabled = fields.Boolean('Cho phép phân tích Gemini', default=False)
    review_auto = fields.Boolean('Tự phân tích khi gắn link Drive', default=False)
    review_model = fields.Char('Model Gemini', default='gemini-3.5-flash-lite', required=True)
    review_max_mb = fields.Integer('Giới hạn tổng video mỗi báo cáo (MB)', default=1024, required=True)
    review_max_minutes = fields.Integer('Giới hạn tổng thời lượng (phút)', default=120, required=True)
    review_api_key = fields.Char(copy=False, groups='base.group_no_one')
    review_key_input = fields.Char('Nhập / thay API key Gemini', compute='_compute_key_input',
                                   inverse='_set_key_input', groups='base.group_system')
    review_key_set = fields.Boolean('Đã lưu API key', compute='_compute_key_input')

    @api.depends('review_api_key')
    def _compute_key_input(self):
        for config in self:
            config.review_key_input = False
            config.review_key_set = bool(config.sudo().review_api_key)

    def _set_key_input(self):
        for config in self:
            config._admin()
            if config.review_key_input:
                config.sudo().review_api_key = config.review_key_input.strip()

    def action_clear_review_key(self):
        self._admin()
        self.sudo().write({'review_api_key': False, 'review_enabled': False})

    def action_test_review_connection(self):
        self._admin()
        if not self.sudo().review_api_key:
            raise UserError('Hãy nhập và lưu API key Gemini trước.')
        from .review import ReviewError
        try:
            with self.env['edu.session.review']._gemini('GET', '/v1beta/models/' + self.review_model) as response:
                response.json()
        except (ReviewError, requests.RequestException, ValueError):
            raise UserError('Chưa kết nối được Gemini với model đã chọn. Kiểm tra API key, tên model và quyền dự án.')
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': 'Gemini', 'message': 'API key và model kết nối thành công.', 'type': 'success'}}

    @api.constrains('review_model', 'review_max_mb', 'review_max_minutes')
    def _check_review_limits(self):
        for config in self:
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', config.review_model or ''):
                raise ValidationError('Tên model Gemini không hợp lệ.')
            if not 16 <= config.review_max_mb <= 2048 or not 1 <= config.review_max_minutes <= 240:
                raise ValidationError('Giới hạn video: 16–2048 MB và 1–240 phút.')

    def _review_ready(self):
        self.ensure_one()
        if not self.review_enabled:
            raise UserError('Hãy bật phân tích Gemini trong cấu hình Google Drive / YouTube.')
        if not self.sudo().review_api_key:
            raise UserError('Chưa cấu hình API key Gemini.')
        if self.drive_state != 'connected' or not self.sudo().refresh_token:
            raise UserError('Cần kết nối Google Drive để phân tích video.')
