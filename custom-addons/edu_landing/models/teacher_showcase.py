import base64

from odoo import api, fields, models
from odoo.tools import file_open


class LandingTeacher(models.Model):
    _name = 'edu.landing.teacher'
    _description = 'Giáo viên trên website'
    _order = 'sequence, id'

    name = fields.Char('Họ và tên', required=True)
    image_1920 = fields.Image('Ảnh giáo viên', required=True, max_width=1920, max_height=1920)
    alt_text = fields.Char('Mô tả ảnh')
    position = fields.Char('Chức danh / chuyên môn')
    certification = fields.Char('Chứng chỉ / thành tích', help='Ví dụ: IELTS 8.5, CELTA, TESOL, SAT 1550.')
    team = fields.Selection([
        ('center', 'Giáo viên tại trung tâm'), ('international', 'Giáo viên nước ngoài'),
    ], string='Nhóm giáo viên', required=True, default='center')
    sequence = fields.Integer('Thứ tự', default=10)
    is_published = fields.Boolean('Hiển thị trên website', default=False)
    website_id = fields.Many2one('website', string='Website', help='Để trống để hiển thị trên mọi website.')

    @api.model
    def _seed_teacher_samples(self):
        parameters = self.env['ir.config_parameter'].sudo()
        marker = 'edu_landing.teacher_samples_created'
        if parameters.get_param(marker):
            return
        samples = [
            ('center', 'Trưởng bộ môn IELTS', 'IELTS 8.5'),
            ('center', 'Quản lý đào tạo', 'CELTA'),
            ('international', 'Giáo viên tiểu học', 'TESOL'),
            ('international', 'Giáo viên SAT', 'SAT 1550'),
        ]
        for index, (team, position, certification) in enumerate(samples, start=1):
            with file_open('edu_landing/static/src/img/teacher_%s.jpg' % index, 'rb') as photo:
                self.create({
                    'name': 'Họ tên giáo viên', 'image_1920': base64.b64encode(photo.read()),
                    'alt_text': 'Ảnh minh hoạ giáo viên', 'position': position,
                    'certification': certification, 'team': team,
                    'sequence': index * 10, 'is_published': True,
                })
        parameters.set_param(marker, '1')
