import os

from odoo import fields, models
from odoo.exceptions import UserError


class LandingActivityUpload(models.TransientModel):
    _name = 'edu.landing.activity.upload'
    _description = 'Tải ảnh sự kiện'

    event_id = fields.Many2one('edu.landing.activity.event', string='Sự kiện', required=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Hình ảnh', required=True)

    def action_upload(self):
        self.ensure_one()
        self.event_id.check_access_rights('write')
        self.event_id.check_access_rule('write')
        if not self.attachment_ids:
            raise UserError('Vui lòng chọn ít nhất một hình ảnh.')
        photos = self.env['edu.landing.activity']
        last = photos.search([('event_id', '=', self.event_id.id)], order='sequence desc', limit=1)
        sequence = last.sequence if last else 0
        values = []
        for attachment in self.attachment_ids:
            if not (attachment.mimetype or '').startswith('image/'):
                raise UserError('Tệp “%s” không phải hình ảnh.' % attachment.name)
            sequence += 10
            values.append({
                'event_id': self.event_id.id,
                'name': os.path.splitext(attachment.name)[0],
                'image_1920': attachment.datas,
                'sequence': sequence,
                'is_published': False,
            })
        photos.create(values)
        return {'type': 'ir.actions.act_window_close'}
