import base64

from odoo import api, fields, models
from odoo.tools import file_open


class LandingActivityEvent(models.Model):
    _name = 'edu.landing.activity.event'
    _description = 'Sự kiện hoạt động lớp học'
    _order = 'date desc, id desc'

    name = fields.Char('Tên sự kiện', required=True, translate=True)
    date = fields.Date('Ngày diễn ra')
    description = fields.Text('Ghi chú')
    active = fields.Boolean('Đang hoạt động', default=True)
    image_ids = fields.One2many('edu.landing.activity', 'event_id', string='Hình ảnh')
    image_count = fields.Integer('Số ảnh', compute='_compute_counts')
    highlight_count = fields.Integer('Ảnh highlight', compute='_compute_counts')

    @api.depends('image_ids', 'image_ids.is_published')
    def _compute_counts(self):
        for event in self:
            event.image_count = len(event.image_ids)
            event.highlight_count = len(event.image_ids.filtered('is_published'))

    def action_upload_images(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tải ảnh sự kiện',
            'res_model': 'edu.landing.activity.upload',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_event_id': self.id},
        }


class LandingActivity(models.Model):
    _name = 'edu.landing.activity'
    _description = 'Ảnh hoạt động lớp học'
    _order = 'sequence, id'

    name = fields.Char('Tiêu đề', required=True, translate=True)
    event_id = fields.Many2one('edu.landing.activity.event', string='Sự kiện',
        required=True, ondelete='cascade', index=True, auto_join=True)
    sequence = fields.Integer('Thứ tự', default=10)
    image_1920 = fields.Image('Hình ảnh', required=True, max_width=1920, max_height=1920,
        help='Hỗ trợ ảnh ngang, dọc và vuông. Website hiển thị trọn ảnh, giữ nguyên tỷ lệ.')
    caption = fields.Text('Chú thích', translate=True)
    alt_text = fields.Char('Mô tả ảnh', translate=True,
        help='Mô tả ngắn nội dung ảnh cho người sử dụng trình đọc màn hình.')
    is_published = fields.Boolean('Highlight', default=False,
        help='Chọn để đưa ảnh vào slideshow trang chủ. Bỏ chọn để chỉ lưu trong sự kiện.')
    website_id = fields.Many2one('website', string='Website',
        help='Để trống để hiển thị trên mọi website.')

    @api.model
    def _seed_activity_samples(self):
        # A separate marker preserves deletions as well as edits on upgrade.
        parameters = self.env['ir.config_parameter'].sudo()
        marker = 'edu_landing.activity_samples_created'
        if parameters.get_param(marker):
            return
        event = self.env['edu.landing.activity.event'].create({'name': 'Hoạt động lớp học — Ảnh mẫu'})
        samples = [
            ('classroom', 'Không gian học tập', 'Mỗi ngày đến lớp là một cơ hội khám phá điều mới.'),
            ('creative', 'Khám phá và sáng tạo', 'Khơi gợi sự tò mò qua những trải nghiệm học tập gần gũi.'),
            ('learning', 'Niềm vui đến lớp', 'Nuôi dưỡng niềm yêu thích học tập từ những điều nhỏ bé.'),
            ('teamwork', 'Cùng nhau tiến bộ', 'Chia sẻ ý tưởng, kết nối và tự tin thể hiện bản thân.'),
        ]
        for index, (filename, title, caption) in enumerate(samples, start=1):
            with file_open('edu_landing/static/src/img/activities/%s.jpg' % filename, 'rb') as photo:
                self.create({
                    'event_id': event.id,
                    'name': '%s — Ảnh minh hoạ' % title,
                    'alt_text': '%s — Ảnh minh hoạ' % title,
                    'caption': caption,
                    'sequence': index * 10,
                    'is_published': True,
                    'image_1920': base64.b64encode(photo.read()),
                })
        parameters.set_param(marker, '1')

    @api.model
    def _organize_activity_events(self):
        # Existing published photos remain highlights; preserve their image data,
        # captions, sequence and website rather than recreating them.
        photos = self.search([('event_id', '=', False)])
        if photos:
            event = self.env['edu.landing.activity.event'].create({'name': 'Hoạt động lớp học hiện có'})
            photos.write({'event_id': event.id})
