import base64

from odoo import api, fields, models
from odoo.tools import file_open


class LandingStudentShowcase(models.Model):
    _name = 'edu.landing.student'
    _description = 'Học viên tiêu biểu trên website'
    _order = 'sequence, id'

    name = fields.Char('Họ và tên', required=True)
    school = fields.Char('Trường đang theo học')
    image_1920 = fields.Image('Ảnh học viên', required=True, max_width=1920, max_height=1920)
    alt_text = fields.Char('Mô tả ảnh')
    category = fields.Selection([
        ('ielts', 'IELTS'), ('cambridge', 'Cambridge'), ('sat', 'SAT'),
    ], string='Nhóm thành tích', required=True, default='ielts')
    exam_label = fields.Char('Chứng chỉ / kỳ thi', help='Ví dụ: IELTS, Flyers, Movers, SAT. Để trống để lấy tên nhóm thành tích.')
    score = fields.Char('Kết quả', help='Ví dụ: 8.0, 1520 hoặc 15/15. Để trống nếu không muốn hiển thị huy hiệu điểm.')
    display_label = fields.Char('Nhãn hiển thị', compute='_compute_display_label')
    description = fields.Text('Thông tin bổ sung')
    sequence = fields.Integer('Thứ tự', default=10)
    is_published = fields.Boolean('Hiển thị trên website', default=False)
    website_id = fields.Many2one('website', string='Website', help='Để trống để hiển thị trên mọi website.')

    @api.depends('category', 'exam_label')
    def _compute_display_label(self):
        labels = dict(self._fields['category'].selection)
        for student in self:
            student.display_label = student.exam_label or labels.get(student.category, '')

    @api.model
    def _seed_student_samples(self):
        parameters = self.env['ir.config_parameter'].sudo()
        marker = 'edu_landing.student_samples_created'
        if parameters.get_param(marker):
            return
        samples = [('ielts', 'IELTS', '8.0'), ('sat', 'SAT', '1520'),
                   ('cambridge', 'Flyers', '15/15'), ('ielts', 'IELTS', '8.5')]
        for index, (category, exam_label, score) in enumerate(samples, start=1):
            with file_open('edu_landing/static/src/img/student_%s.jpg' % index, 'rb') as photo:
                self.create({
                    'name': 'Tên học viên', 'school': 'Trường đang theo học',
                    'image_1920': base64.b64encode(photo.read()),
                    'alt_text': 'Ảnh minh hoạ học viên', 'category': category,
                    'exam_label': exam_label, 'score': score, 'sequence': index * 10,
                    'is_published': True,
                })
        parameters.set_param(marker, '1')
