# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EduPayrollLine(models.Model):
    _name = 'edu.payroll.line'
    _description = 'Chi tiết lương giáo viên theo kỳ'
    _order = 'period_id, teacher_type, teacher_id'

    period_id = fields.Many2one('edu.payroll.period', 'Kỳ lương', required=True, ondelete='cascade', index=True)
    teacher_id = fields.Many2one('edu.teacher', 'Giáo viên', required=True, index=True)
    teacher_type = fields.Selection(related='teacher_id.teacher_type', store=True)
    agency_id = fields.Many2one(related='teacher_id.agency_id', store=True)
    session_count = fields.Integer('Số buổi')
    hours = fields.Float('Số giờ')
    rate_end_month = fields.Float('Đơn giá cuối tháng (đ/giờ)', digits=(16, 0))
    amount = fields.Float('Lương nội bộ (đ)', digits=(16, 2))
    warning_count = fields.Integer('Buổi có cảnh báo')
    agency_hours = fields.Float('Giờ Agency')
    agency_amount = fields.Float('Lương Agency (đ)', digits=(16, 2))
    diff_hours = fields.Float('Lệch giờ', compute='_compute_diff', store=True)
    diff_amount = fields.Float('Lệch lương (đ)', digits=(16, 2), compute='_compute_diff', store=True)
    status = fields.Selection(
        [('no_session', 'Không có buổi dạy'), ('no_rate', 'Chưa có đơn giá'),
         ('warning', 'Có cảnh báo'), ('agency_diff', 'Lệch Agency'), ('ok', 'OK')],
        string='Trạng thái', compute='_compute_status', store=True)

    _sql_constraints = [
        ('period_teacher_uniq', 'unique(period_id, teacher_id)', 'Giáo viên đã có trong kỳ lương này.'),
    ]

    @api.depends('hours', 'amount', 'agency_hours', 'agency_amount')
    def _compute_diff(self):
        for rec in self:
            entered = bool(rec.agency_hours or rec.agency_amount)
            rec.diff_hours = rec.agency_hours - rec.hours if entered else 0.0
            rec.diff_amount = rec.agency_amount - rec.amount if entered else 0.0

    @api.depends('session_count', 'rate_end_month', 'warning_count', 'diff_hours', 'diff_amount',
                 'agency_hours', 'agency_amount')
    def _compute_status(self):
        for rec in self:
            if not rec.session_count:
                rec.status = 'no_session'
            elif not rec.rate_end_month:
                rec.status = 'no_rate'
            elif rec.warning_count:
                rec.status = 'warning'
            elif (rec.agency_hours or rec.agency_amount) and (
                    abs(rec.diff_hours) > 0.01 or abs(rec.diff_amount) > 1):
                rec.status = 'agency_diff'
            else:
                rec.status = 'ok'
