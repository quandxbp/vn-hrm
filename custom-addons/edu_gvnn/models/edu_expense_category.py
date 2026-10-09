# -*- coding: utf-8 -*-
from odoo import fields, models


class EduExpenseCategory(models.Model):
    _name = 'edu.expense.category'
    _description = 'Danh mục chi phí khác'
    _order = 'sequence, name'

    name = fields.Char('Tên', required=True)
    sequence = fields.Integer('Thứ tự', default=10)
    active = fields.Boolean('Đang hoạt động', default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Danh mục chi phí đã tồn tại.'),
    ]
