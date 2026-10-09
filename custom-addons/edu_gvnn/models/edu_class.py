# -*- coding: utf-8 -*-
from odoo import api, fields, models

from ..tools import normalize_name


class EduClass(models.Model):
    _name = 'edu.class'
    _description = 'Lớp'
    _order = 'name'

    name = fields.Char('Tên lớp', required=True)
    zalo_group = fields.Char('Nhóm Zalo')
    teacher_ids = fields.Many2many(
        'edu.teacher', 'edu_class_teacher_rel', 'class_id', 'teacher_id', 'Giáo viên phụ trách')
    student_ids = fields.Many2many(
        'edu.student', 'edu_student_class_rel', 'class_id', 'student_id', 'Học viên')
    student_count = fields.Integer('Số học viên', compute='_compute_student_count')
    note = fields.Text('Ghi chú')
    active = fields.Boolean('Đang hoạt động', default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Tên lớp đã tồn tại.'),
    ]

    @api.depends('student_ids')
    def _compute_student_count(self):
        for rec in self:
            rec.student_count = len(rec.student_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = normalize_name(vals.get('name'))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = normalize_name(vals['name'])
        return super().write(vals)
