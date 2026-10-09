# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Ngày xa tuần cuối hơn mức này thì không tự tạo tuần, tránh sinh hàng loạt tuần khi gõ nhầm năm.
MAX_AUTO_GAP_DAYS = 90


class EduWeek(models.Model):
    """Tuần theo cách đánh số riêng của trung tâm (tuần 1 bắt đầu 10/10/2024), không phải tuần ISO."""
    _name = 'edu.week'
    _description = 'Tuần'
    _order = 'number desc'

    name = fields.Char('Tên', compute='_compute_name', store=True)
    number = fields.Integer('Số tuần', required=True)
    date_from = fields.Date('Từ ngày', required=True)
    date_to = fields.Date('Đến ngày', required=True)

    _sql_constraints = [
        ('number_uniq', 'unique(number)', 'Số tuần đã tồn tại.'),
    ]

    @api.depends('number', 'date_from', 'date_to')
    def _compute_name(self):
        for week in self:
            if week.date_from and week.date_to:
                week.name = 'Tuần %s (%s - %s)' % (
                    week.number, week.date_from.strftime('%d/%m'), week.date_to.strftime('%d/%m/%Y'))
            else:
                week.name = 'Tuần %s' % week.number

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for week in self:
            if week.date_from > week.date_to:
                raise ValidationError('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')
            overlap = self.search_count([
                ('id', '!=', week.id),
                ('date_from', '<=', week.date_to),
                ('date_to', '>=', week.date_from),
            ])
            if overlap:
                raise ValidationError('Khoảng ngày của tuần bị trùng với tuần khác.')

    @api.model
    def _get_week(self, date, create=True):
        """Tuần chứa `date`. Nếu `date` sau tuần cuối thì tự tạo các tuần nối tiếp (thứ Hai đến Chủ nhật).

        Ngày nằm trước tuần đầu hoặc trong khoảng trống giữa các tuần thì trả về rỗng, người dùng phải tạo tuần.
        """
        week = self.search([('date_from', '<=', date), ('date_to', '>=', date)], limit=1)
        if week or not create:
            return week
        last = self.search([], order='date_to desc', limit=1)
        if not last or date <= last.date_to or (date - last.date_to).days > MAX_AUTO_GAP_DAYS:
            return week
        Week = self.sudo()
        number, start = last.number, last.date_to + timedelta(days=1)
        while True:
            number += 1
            end = start + timedelta(days=6)
            week = Week.create({'number': number, 'date_from': start, 'date_to': end})
            if end >= date:
                return week
            start = end + timedelta(days=1)
