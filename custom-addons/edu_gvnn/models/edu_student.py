# -*- coding: utf-8 -*-
from odoo import api, fields, models

from ..tools import get_param, normalize_name


class EduStudent(models.Model):
    _name = 'edu.student'
    _description = 'Học viên'
    _inherit = ['mail.thread', 'image.mixin']
    _order = 'code'

    image_1920 = fields.Image(string='Avatar')

    code = fields.Char(
        'Mã HV', required=True, copy=False, tracking=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('edu.student'))
    name_vi = fields.Char('Tên tiếng Việt', required=True, tracking=True)
    name_en = fields.Char('Tên tiếng Anh', tracking=True)
    name = fields.Char('Việt - Anh', compute='_compute_name', store=True)
    class_ids = fields.Many2many(
        'edu.class', 'edu_student_class_rel', 'student_id', 'class_id', 'Lớp')
    zalo_group = fields.Char('Nhóm Zalo')
    parent_name = fields.Char('Phụ huynh')
    phone = fields.Char('Điện thoại')
    state = fields.Selection(
        [('studying', 'Đang học'), ('stopped', 'Ngưng học')],
        string='Tình trạng', required=True, default='studying', tracking=True)
    opening_date = fields.Date('Ngày bắt đầu tính số dư')
    opening_balance = fields.Float('Số dư đầu kỳ', digits=(16, 2))
    note = fields.Text('Ghi chú')
    active = fields.Boolean('Đang hoạt động', default=True)

    payment_ids = fields.One2many('edu.tuition.payment', 'student_id', 'Phiếu thu')
    attendee_ids = fields.One2many('edu.session.attendee', 'student_id', 'Lượt tham dự')
    total_paid = fields.Float('Đã thu (đ)', digits=(16, 2), compute='_compute_balance', store=True)
    learned_hours = fields.Float('Giờ đã học', compute='_compute_balance', store=True)
    learned_blocks = fields.Float('Buổi đã học', compute='_compute_balance', store=True)
    learned_amount = fields.Float('Tiền đã học (đ)', digits=(16, 2), compute='_compute_balance', store=True)
    balance = fields.Float('Số dư học phí (đ)', digits=(16, 2), compute='_compute_balance', store=True)
    remaining_blocks = fields.Float('Buổi còn lại', compute='_compute_balance', store=True)
    last_session_date = fields.Date('Buổi gần nhất', compute='_compute_balance', store=True)
    fee_warning = fields.Selection(
        [('out', 'Hết học phí'), ('low', 'Gần hết học phí')],
        string='Cảnh báo học phí', compute='_compute_fee_warning', store=True, index=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Mã học viên đã tồn tại.'),
        ('name_uniq', 'unique(name)', 'Học viên có tên "Việt - Anh" này đã tồn tại.'),
    ]

    @api.depends('name_vi', 'name_en')
    def _compute_name(self):
        for rec in self:
            rec.name = ' - '.join(p for p in (rec.name_vi, rec.name_en) if p)

    @api.depends(
        'opening_balance', 'opening_date', 'payment_ids.amount', 'payment_ids.date',
        'attendee_ids.charge_amount', 'attendee_ids.charge_hours', 'attendee_ids.blocks',
        'attendee_ids.date', 'attendee_ids.present', 'attendee_ids.session_state')
    def _compute_balance(self):
        """Chỉ tính các khoản từ `opening_date` trở đi; trước đó đã gộp vào `opening_balance`."""
        price = get_param(self.env, 'block_price', 100000.0) or 100000.0
        for rec in self:
            since = rec.opening_date
            payments = rec.payment_ids.filtered(lambda p: not since or p.date >= since)
            attendees = rec.attendee_ids.filtered(lambda a: not since or a.date >= since)
            rec.total_paid = sum(payments.mapped('amount'))
            rec.learned_hours = sum(attendees.mapped('charge_hours'))
            rec.learned_blocks = sum(attendees.mapped('blocks'))
            rec.learned_amount = sum(attendees.mapped('charge_amount'))
            rec.balance = rec.opening_balance + rec.total_paid - rec.learned_amount
            rec.remaining_blocks = rec.balance / price
            rec.last_session_date = max(
                (a.date for a in rec.attendee_ids
                 if a.present and a.session_state == 'done' and a.session_type == 'lesson'),
                default=False)

    @api.depends('balance', 'state')
    def _compute_fee_warning(self):
        out = get_param(self.env, 'fee_out_threshold', 1.0)
        low = get_param(self.env, 'fee_low_threshold', 300000.0)
        for rec in self:
            if rec.state != 'studying':
                rec.fee_warning = False
            elif rec.balance < out:
                rec.fee_warning = 'out'
            elif rec.balance < low:
                rec.fee_warning = 'low'
            else:
                rec.fee_warning = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_vals(vals)
        return super().write(vals)

    @api.model
    def _normalize_vals(self, vals):
        for field in ('name_vi', 'name_en'):
            if vals.get(field):
                vals[field] = normalize_name(vals[field])

    def action_stop(self):
        self.write({'state': 'stopped'})

    def action_resume(self):
        self.write({'state': 'studying'})

    def action_new_payment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Thu học phí', 'res_model': 'edu.tuition.payment',
            'view_mode': 'form', 'target': 'current', 'context': {'default_student_id': self.id},
        }
