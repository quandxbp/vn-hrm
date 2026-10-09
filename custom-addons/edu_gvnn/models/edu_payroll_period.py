# -*- coding: utf-8 -*-
import calendar
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class EduPayrollPeriod(models.Model):
    _name = 'edu.payroll.period'
    _description = 'Kỳ lương giáo viên'
    _inherit = ['mail.thread']
    _order = 'date_from desc'

    name = fields.Char('Kỳ lương', compute='_compute_name', store=True)
    date_from = fields.Date(
        'Từ ngày', required=True, tracking=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
        help='Ngày đầu tiên của tháng.')
    date_to = fields.Date('Đến ngày', compute='_compute_name', store=True)
    state = fields.Selection(
        [('open', 'Đang mở'), ('locked', 'Đã chốt')], string='Trạng thái',
        required=True, default='open', tracking=True)
    line_ids = fields.One2many('edu.payroll.line', 'period_id', 'Chi tiết theo giáo viên')
    total_hours = fields.Float('Tổng giờ', compute='_compute_totals')
    total_amount = fields.Float('Tổng lương (đ)', digits=(16, 2), compute='_compute_totals')
    locked_by = fields.Many2one('res.users', 'Người chốt', readonly=True, copy=False)
    locked_date = fields.Datetime('Thời điểm chốt', readonly=True, copy=False)

    _sql_constraints = [
        ('date_from_uniq', 'unique(date_from)', 'Tháng này đã có kỳ lương.'),
    ]

    @api.depends('date_from')
    def _compute_name(self):
        for rec in self:
            if rec.date_from:
                rec.name = 'Lương %s' % rec.date_from.strftime('%m/%Y')
                rec.date_to = rec.date_from.replace(
                    day=calendar.monthrange(rec.date_from.year, rec.date_from.month)[1])
            else:
                rec.name = rec.date_to = False

    @api.depends('line_ids.hours', 'line_ids.amount')
    def _compute_totals(self):
        for rec in self:
            rec.total_hours = sum(rec.line_ids.mapped('hours'))
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    @api.constrains('date_from')
    def _check_first_day(self):
        for rec in self:
            if rec.date_from.day != 1:
                raise ValidationError('Kỳ lương phải bắt đầu từ ngày 1 của tháng.')

    def _get_sessions(self, teacher=None):
        self.ensure_one()
        domain = [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        if teacher:
            domain.append(('teacher_id', '=', teacher.id))
        return self.env['edu.session'].sudo().search(domain, order='date, time_start, id')

    def action_compute(self):
        for period in self:
            if period.state == 'locked':
                raise UserError('Kỳ lương đã chốt, hãy mở khoá trước khi tính lại.')
            by_teacher = defaultdict(lambda: self.env['edu.session'])
            for session in period._get_sessions():
                by_teacher[session.teacher_id] |= session
            existing = {line.teacher_id.id: line for line in period.line_ids}
            for teacher, sessions in by_teacher.items():
                paid = sessions.filtered(lambda s: s.paid_hours > 0)
                vals = {
                    'session_count': len(paid),
                    'hours': sum(paid.mapped('paid_hours')),
                    'amount': sum(paid.mapped('teacher_amount')),
                    'rate_end_month': teacher._get_rate(period.date_to),
                    'warning_count': len(sessions.filtered(
                        lambda s: s.state == 'done' and s.warning != 'ok')),
                }
                line = existing.pop(teacher.id, None)
                if line:
                    line.write(vals)
                else:
                    self.env['edu.payroll.line'].create(dict(vals, period_id=period.id, teacher_id=teacher.id))
            for line in existing.values():
                if line.agency_hours or line.agency_amount:
                    line.write({'session_count': 0, 'hours': 0.0, 'amount': 0.0, 'warning_count': 0})
                else:
                    line.unlink()
        return True

    def action_lock(self):
        for period in self:
            if period.state == 'locked':
                continue
            period.action_compute()
            period._get_sessions().with_context(edu_payroll_internal=True).write({'paid': True})
            period.write({'state': 'locked', 'locked_by': self.env.user.id,
                          'locked_date': fields.Datetime.now()})
            period.message_post(body='Đã chốt lương, khoá các buổi học trong tháng.')
        return True

    def action_unlock(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError('Chỉ Admin mới được mở khoá kỳ lương.')
        for period in self:
            if period.state != 'locked':
                continue
            period._get_sessions().with_context(edu_payroll_internal=True).write({'paid': False})
            period.write({'state': 'open', 'locked_by': False, 'locked_date': False})
            period.message_post(body='Admin %s đã mở khoá kỳ lương.' % self.env.user.name)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        periods = super().create(vals_list)
        periods.action_compute()
        return periods

    def unlink(self):
        if any(p.state == 'locked' for p in self):
            raise UserError('Không xoá được kỳ lương đã chốt.')
        return super().unlink()
