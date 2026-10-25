from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SessionRecordingPart(models.Model):
    _name = 'edu.session.recording.part'
    _description = 'Đoạn video bổ sung của buổi học'
    _order = 'number, id'
    _rec_name = 'name'

    session_id = fields.Many2one('edu.session', required=True, ondelete='cascade', index=True)
    number = fields.Integer('Phần', required=True, default=2)
    name = fields.Char(compute='_compute_name')
    google_drive_url = fields.Char('Link Google Drive', required=True)
    youtube_url = fields.Char('Link YouTube', copy=False)

    _sql_constraints = [
        ('session_number_unique', 'unique(session_id, number)', 'Số phần đã tồn tại trong buổi học.'),
        ('number_minimum', 'CHECK(number >= 2)', 'Đoạn bổ sung phải từ Phần 2 trở đi.'),
    ]

    @api.depends('number')
    def _compute_name(self):
        for part in self:
            part.name = 'Phần %s' % part.number

    def _check_parent_access(self):
        sessions = self.mapped('session_id')
        sessions.check_access_rights('write')
        sessions.check_access_rule('write')

    def _check_video_history(self):
        """Extended by edu_video; never detach a part from upload history."""

    @api.constrains('google_drive_url', 'session_id')
    def _check_drive(self):
        for part in self:
            if not self.env['edu.public.schedule']._drive_link(part.google_drive_url):
                raise ValidationError('Link phải là Google Drive hoặc Google Docs hợp lệ.')
            if not part.session_id.google_drive_url:
                raise ValidationError('Cần nhập link Drive Phần 1 trước khi thêm đoạn.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            session = self.env['edu.session'].browse(vals['session_id'])
            session.check_access_rights('write')
            session.check_access_rule('write')
            vals['google_drive_url'] = (vals.get('google_drive_url') or '').strip()
        return super().create(vals_list)

    def write(self, vals):
        self._check_parent_access()
        if 'session_id' in vals and any(p.session_id.id != vals['session_id'] for p in self):
            raise UserError('Không chuyển đoạn video sang buổi học khác.')
        if 'google_drive_url' in vals:
            vals['google_drive_url'] = (vals['google_drive_url'] or '').strip()
            changed = self.filtered(lambda p: p.google_drive_url != vals['google_drive_url'])
            if any(p.youtube_url for p in changed) and vals.get('youtube_url', True):
                raise UserError('Đoạn đã có YouTube. Hãy kiểm tra và bỏ link YouTube trước khi thay video gốc.')
            changed._check_video_history()
        return super().write(vals)

    def unlink(self):
        self._check_parent_access()
        if any(self.mapped('youtube_url')):
            raise UserError('Đoạn đã có link YouTube, không thể xóa trực tiếp.')
        self._check_video_history()
        return super().unlink()
