# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..tools import amount_in_words, get_param


class EduTuitionPayment(models.Model):
    _name = 'edu.tuition.payment'
    _description = 'Phiếu thu / chi học phí'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    ref = fields.Char('Số phiếu', readonly=True, copy=False, default='/')
    student_id = fields.Many2one(
        'edu.student', 'Học viên', required=True, index=True, tracking=True)
    date = fields.Date('Ngày', required=True, default=fields.Date.context_today, index=True, tracking=True)
    payment_type = fields.Selection(
        [('payment', 'Thu học phí'), ('refund', 'Hoàn tiền')],
        string='Loại', required=True, default='payment', index=True)
    blocks = fields.Float(
        'Số buổi', default=lambda self: get_param(self.env, 'default_blocks', 20.0))
    block_price = fields.Float(
        'Đơn giá/buổi (đ)', digits=(16, 0),
        default=lambda self: get_param(self.env, 'block_price', 100000.0))
    gross_amount = fields.Float(
        'Thành tiền (đ)', digits=(16, 2),
        default=lambda self: get_param(self.env, 'default_blocks', 20.0)
        * get_param(self.env, 'block_price', 100000.0))
    discount_amount = fields.Float('Giảm giá (đ)', digits=(16, 2))
    amount = fields.Float(
        'Thực thu (đ)', digits=(16, 2), compute='_compute_amount', store=True, tracking=True,
        help='Số tiền thực thu, mang dấu âm với phiếu hoàn tiền.')
    method = fields.Selection(
        [('cash', 'Tiền mặt'), ('transfer', 'Chuyển khoản'), ('other', 'Khác')],
        string='Hình thức', required=True, default='cash')
    payer_name = fields.Char('Người nộp / nhận tiền')
    note = fields.Char('Ghi chú')
    user_id = fields.Many2one('res.users', 'Người lập phiếu', default=lambda self: self.env.user, copy=False)
    amount_text = fields.Char('Bằng chữ', compute='_compute_amount_text')
    import_key = fields.Char('Khoá import', copy=False, index=True)

    _sql_constraints = [
        ('import_key_uniq', 'unique(import_key)', 'Phiếu này đã được import.'),
        ('amounts_positive', 'check(gross_amount >= 0 and discount_amount >= 0)',
         'Thành tiền và giảm giá không được âm.'),
    ]

    @api.depends('gross_amount', 'discount_amount', 'payment_type')
    def _compute_amount(self):
        for rec in self:
            net = rec.gross_amount - rec.discount_amount
            rec.amount = -net if rec.payment_type == 'refund' else net

    @api.depends('amount')
    def _compute_amount_text(self):
        for rec in self:
            rec.amount_text = amount_in_words(rec.amount)

    @api.constrains('gross_amount', 'discount_amount')
    def _check_discount(self):
        for rec in self:
            if rec.discount_amount > rec.gross_amount:
                raise ValidationError('Giảm giá không được lớn hơn thành tiền.')

    @api.onchange('blocks', 'block_price')
    def _onchange_blocks(self):
        self.gross_amount = self.blocks * self.block_price

    @api.onchange('gross_amount')
    def _onchange_gross_amount(self):
        if self.block_price:
            self.blocks = self.gross_amount / self.block_price

    @api.onchange('student_id')
    def _onchange_student_id(self):
        if self.student_id and not self.payer_name:
            self.payer_name = self.student_id.parent_name

    def _check_refund_rights(self, vals_list):
        if self.env.su or self.env.user.has_group('edu_gvnn.group_edu_manager'):
            return
        if any(v.get('payment_type') == 'refund' for v in vals_list):
            raise AccessError('Chỉ Quản lý mới được lập phiếu hoàn tiền.')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_refund_rights(vals_list)
        for vals in vals_list:
            if not vals.get('ref') or vals['ref'] == '/':
                code = 'edu.tuition.refund' if vals.get('payment_type') == 'refund' else 'edu.tuition.payment'
                vals['ref'] = self.env['ir.sequence'].next_by_code(code) or '/'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('payment_type') == 'refund' or any(r.payment_type == 'refund' for r in self):
            self._check_refund_rights([{'payment_type': 'refund'}])
        return super().write(vals)
