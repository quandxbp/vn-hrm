# -*- coding: utf-8 -*-
from odoo import api, fields, models

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = normalize_name(vals.get('name'))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = normalize_name(vals['name'])
        return super().write(vals)
