# -*- coding: utf-8 -*-
from odoo import fields, models


class EduOtherExpense(models.Model):
    _name = 'edu.other.expense'
    _description = 'Chi phí khác'
    _order = 'date desc, id desc'

    date = fields.Date('Ngày', required=True, default=fields.Date.context_today, index=True)
    name = fields.Char('Nội dung', required=True)
    category_id = fields.Many2one('edu.expense.category', 'Danh mục', required=True)
    amount = fields.Float('Số tiền (đ)', digits=(16, 2), required=True)
    note = fields.Char('Ghi chú')

    _sql_constraints = [
        ('amount_positive', 'check(amount >= 0)', 'Số tiền không được âm.'),
    ]
