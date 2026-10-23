# -*- coding: utf-8 -*-
from urllib.parse import urlsplit

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import normalize_name


class EduTeacher(models.Model):
    _name = 'edu.teacher'
    _description = 'Giáo viên'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char('Tên giáo viên', required=True, tracking=True)
    code = fields.Char('Mã')
    teacher_type = fields.Selection(
        [('agency', 'Qua Agency'), ('direct', 'Làm trực tiếp')],
        string='Loại giáo viên', required=True, default='agency', tracking=True)
    agency_id = fields.Many2one('res.partner', 'Agency', tracking=True)
    phone = fields.Char('Điện thoại')
    email = fields.Char('Email')
    teaching_title = fields.Selection(
        [('mr', 'Thầy'), ('ms', 'Cô')], string='Danh xưng', tracking=True,
        help='Dùng trong lịch học gửi Zalo. Chưa chọn thì hiển thị GV.')
    meeting_url = fields.Char(
        'Link học', tracking=True, help='Link Google Meet hoặc Zoom của giáo viên, bắt đầu bằng https://.')
    note = fields.Text('Ghi chú')
    active = fields.Boolean('Đang hoạt động', default=True)
    rate_ids = fields.One2many(
        'edu.teacher.rate', 'teacher_id', 'Lịch sử đơn giá',
        groups='edu_gvnn.group_edu_manager')
    current_rate = fields.Float(
        'Đơn giá hiện tại (đ/giờ)', digits=(16, 0), compute='_compute_current_rate',
        groups='edu_gvnn.group_edu_manager')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Tên giáo viên đã tồn tại.'),
    ]

    @api.depends('rate_ids.date_from', 'rate_ids.rate')
    def _compute_current_rate(self):
        today = fields.Date.context_today(self)
        for teacher in self:
            teacher.current_rate = teacher._get_rate(today)

    def _get_rate(self, date):
        """Đơn giá/giờ có hiệu lực tại `date`: dòng có ngày hiệu lực gần nhất không quá `date`."""
        self.ensure_one()
        rates = self.sudo().rate_ids.filtered(lambda r: r.date_from <= date)
        return rates.sorted('date_from')[-1].rate if rates else 0.0

    def _schedule_label(self):
        self.ensure_one()
        title = {'mr': 'Thầy', 'ms': 'Cô'}.get(self.teaching_title, 'GV')
        return '%s %s' % (title, self.name)

    @api.constrains('meeting_url')
    def _check_meeting_url(self):
        for teacher in self:
            if not teacher.meeting_url:
                continue
            try:
                url = urlsplit(teacher.meeting_url)
                valid = (url.scheme in ('https', 'http') and url.hostname
                         and not url.username and not url.password
                         and not any(c.isspace() for c in teacher.meeting_url))
            except ValueError:
                valid = False
            if not valid:
                raise ValidationError('Link học phải là URL đầy đủ bắt đầu bằng https:// hoặc http://.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = normalize_name(vals.get('name'))
            if vals.get('meeting_url'):
                vals['meeting_url'] = vals['meeting_url'].strip()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('meeting_url'):
            vals['meeting_url'] = vals['meeting_url'].strip()
        if vals.get('name'):
            vals['name'] = normalize_name(vals['name'])
        return super().write(vals)
