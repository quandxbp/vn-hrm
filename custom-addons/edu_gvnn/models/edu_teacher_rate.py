# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class EduTeacherRate(models.Model):
    _name = 'edu.teacher.rate'
    _description = 'Lịch sử đơn giá giáo viên'
    _order = 'teacher_id, date_from desc'

    teacher_id = fields.Many2one(
        'edu.teacher', 'Giáo viên', required=True, ondelete='cascade', index=True)
    date_from = fields.Date('Ngày hiệu lực', required=True)
    rate = fields.Float('Đơn giá (đ/giờ)', digits=(16, 0), required=True)
    note = fields.Char('Ghi chú')

    _sql_constraints = [
        ('teacher_date_uniq', 'unique(teacher_id, date_from)',
         'Giáo viên đã có đơn giá tại ngày hiệu lực này.'),
        ('rate_positive', 'check(rate >= 0)', 'Đơn giá không được âm.'),
    ]

    def _check_not_paid(self):
        """Không sửa hoặc xoá đơn giá đã dùng tính lương cho buổi đã trả lương."""
        for rate in self:
            used = self.env['edu.session'].sudo().search_count([
                ('teacher_id', '=', rate.teacher_id.id), ('date', '>=', rate.date_from),
                ('paid', '=', True)])
            if used:
                raise UserError(
                    'Giáo viên %s đã có buổi đã trả lương từ %s, không sửa hoặc xoá đơn giá này. '
                    'Hãy thêm một dòng đơn giá mới.' % (rate.teacher_id.name, rate.date_from))

    @api.model
    def _check_month_open(self, dates):
        """Không thêm, sửa, xoá đơn giá có ngày hiệu lực nằm trong tháng đã chốt lương."""
        Period = self.env['edu.payroll.period'].sudo()
        for date in filter(None, dates):
            if Period.search_count([
                    ('state', '=', 'locked'), ('date_from', '<=', date), ('date_to', '>=', date)]):
                raise UserError(
                    'Tháng của ngày %s đã chốt lương, không thêm, sửa hoặc xoá đơn giá có hiệu lực '
                    'trong tháng này. Hãy thêm đơn giá mới với ngày hiệu lực ở tháng chưa chốt.' % date)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_month_open([v.get('date_from') for v in vals_list])
        rates = super().create(vals_list)
        rates._recompute_sessions()
        return rates

    def write(self, vals):
        if {'rate', 'date_from', 'teacher_id'} & set(vals):
            self._check_not_paid()
            self._check_month_open(self.mapped('date_from') + [vals.get('date_from')])
        old = [(r.teacher_id, r.date_from) for r in self]
        res = super().write(vals)
        for teacher, date_from in old:
            self.env['edu.session']._recompute_rates(teacher, date_from)
        self._recompute_sessions()
        return res

    def unlink(self):
        self._check_not_paid()
        self._check_month_open(self.mapped('date_from'))
        old = [(r.teacher_id, r.date_from) for r in self]
        res = super().unlink()
        for teacher, date_from in old:
            self.env['edu.session']._recompute_rates(teacher, date_from)
        return res

    def _recompute_sessions(self):
        for rate in self:
            self.env['edu.session']._recompute_rates(rate.teacher_id, rate.date_from)
