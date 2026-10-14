import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LandingCourse(models.Model):
    _name = 'edu.landing.course'
    _description = 'Khóa học trên website'
    _order = 'sequence, id'

    name = fields.Char('Tên khóa học', required=True, translate=True)
    slug = fields.Char('Đường dẫn khóa học', required=True, copy=False)
    sequence = fields.Integer('Thứ tự', default=10)
    is_published = fields.Boolean('Hiển thị trên website', default=False)
    website_id = fields.Many2one('website', string='Website', help='Để trống để sử dụng trên các website.')
    age_range = fields.Char('Độ tuổi', required=True, translate=True)
    target = fields.Char('Mục tiêu học tập', required=True, translate=True)
    introduction = fields.Text('Giới thiệu ngắn', translate=True)
    description = fields.Html('Nội dung giới thiệu', translate=True, sanitize=True)
    image_1920 = fields.Image('Ảnh khóa học', max_width=1920, max_height=1920)
    fallback_image = fields.Char('Ảnh mặc định', groups='website.group_website_designer')
    program_value = fields.Selection([
        ('Tiếng Anh mầm non', 'Tiếng Anh mầm non'),
        ('Tiếng Anh tiểu học', 'Tiếng Anh tiểu học'),
        ('Tiếng Anh thiếu niên', 'Tiếng Anh thiếu niên'),
        ('IELTS / SAT', 'IELTS / SAT'),
        ('Chưa xác định', 'Chưa xác định'),
    ], string='Chương trình trên form tư vấn', default='Chưa xác định', required=True)
    seats_confirmed = fields.Boolean('Đã cập nhật số lượng còn nhận', default=False)
    seats_remaining = fields.Integer('Số học viên còn nhận', default=0,
        help='Cập nhật thủ công theo đợt tuyển sinh. Gửi form tư vấn không tự trừ số lượng này.')

    _sql_constraints = [('slug_unique', 'unique(slug)', 'Đường dẫn khóa học đã được sử dụng.')]

    @api.constrains('seats_remaining', 'slug')
    def _check_course_values(self):
        for course in self:
            if course.seats_remaining < 0:
                raise ValidationError('Số học viên còn nhận không được nhỏ hơn 0.')
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', course.slug or ''):
                raise ValidationError('Đường dẫn chỉ gồm chữ thường không dấu, số và dấu gạch ngang.')

    def action_open_website(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': '/khoa-hoc/%s' % self.slug, 'target': 'new'}
