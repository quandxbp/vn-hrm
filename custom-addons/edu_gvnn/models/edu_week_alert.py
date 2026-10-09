# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models

from ..tools import get_param

PRIORITY_ACTIONS = {
    'red_now': 'Gọi phụ huynh + xác nhận lịch học và học phí',
    'red': 'Liên hệ trong ngày',
    'yellow': 'Theo dõi và nhắc trong tuần',
    'ok': 'Không cần xử lý',
}


class EduWeekAlert(models.Model):
    _name = 'edu.week.alert'
    _description = 'Cảnh báo tuần'
    _order = 'week_id desc, priority_order, student_id'

    week_id = fields.Many2one('edu.week', 'Tuần', required=True, ondelete='cascade', index=True)
    student_id = fields.Many2one('edu.student', 'Học viên', required=True, ondelete='cascade', index=True)
    class_ids = fields.Many2many(related='student_id.class_ids')
    hours_n0 = fields.Float('Giờ tuần này')
    hours_n1 = fields.Float('Giờ tuần N-1')
    hours_n2 = fields.Float('Giờ tuần N-2')
    absent_streak = fields.Integer('Số tuần nghỉ liên tiếp')
    absent = fields.Boolean('Nghỉ trong tuần')
    absent_3w = fields.Boolean('Nghỉ nhiều tuần liên tiếp')
    suggest_stop = fields.Boolean('Đề xuất ngưng học')
    session_count = fields.Integer('Số buổi trong tuần')
    last_session_date = fields.Date('Buổi gần nhất')
    fee_warning = fields.Selection(
        [('out', 'Hết học phí'), ('low', 'Gần hết học phí')], string='Cảnh báo học phí')
    balance = fields.Float('Số dư (đ)', digits=(16, 2))
    remaining_blocks = fields.Float('Buổi còn lại')
    warning_sessions = fields.Integer('Buổi có cảnh báo')
    priority = fields.Selection(
        [('red_now', 'ĐỎ - LIÊN HỆ NGAY'), ('red', 'ĐỎ'), ('yellow', 'VÀNG'), ('ok', 'ỔN')],
        string='Mức độ ưu tiên', required=True, default='ok', index=True)
    priority_order = fields.Integer(compute='_compute_priority_order', store=True)
    action = fields.Char('Hành động đề xuất', compute='_compute_action', store=True)
    contacted = fields.Boolean('Đã liên hệ')
    contact_note = fields.Char('Ghi chú liên hệ')
    student_state = fields.Selection(related='student_id.state')

    _sql_constraints = [
        ('week_student_uniq', 'unique(week_id, student_id)', 'Học viên đã có cảnh báo trong tuần này.'),
    ]

    @api.depends('priority')
    def _compute_priority_order(self):
        order = {'red_now': 0, 'red': 1, 'yellow': 2, 'ok': 3}
        for rec in self:
            rec.priority_order = order.get(rec.priority, 3)

    @api.depends('priority')
    def _compute_action(self):
        for rec in self:
            rec.action = PRIORITY_ACTIONS.get(rec.priority, '')

    @api.model
    def _generate(self, week):
        """Tạo hoặc cập nhật cảnh báo của `week` cho học viên đang học; giữ nguyên ghi chú liên hệ."""
        absent_weeks = int(get_param(self.env, 'absent_weeks', 3))
        stop_weeks = int(get_param(self.env, 'stop_suggest_weeks', 4))
        depth = max(absent_weeks, stop_weeks, 3)
        numbers = [week.number - i for i in range(depth)]
        attendees = self.env['edu.session.attendee'].search([
            ('week_id.number', 'in', numbers), ('present', '=', True),
            ('session_state', '=', 'done'), ('session_type', '=', 'lesson')])
        hours = defaultdict(lambda: defaultdict(float))
        sessions_n0 = defaultdict(int)
        warnings_n0 = defaultdict(int)
        for att in attendees:
            number = att.week_id.number
            hours[att.student_id.id][number] += att.charge_hours
            if number == week.number:
                sessions_n0[att.student_id.id] += 1
                if att.session_id.warning != 'ok':
                    warnings_n0[att.student_id.id] += 1

        students = self.env['edu.student'].search([('state', '=', 'studying')])
        existing = {a.student_id.id: a for a in self.search([('week_id', '=', week.id)])}
        for student in students:
            h = hours[student.id]
            streak = 0
            while streak < depth and not h.get(week.number - streak):
                streak += 1
            absent = not h.get(week.number)
            absent_3w = streak >= absent_weeks
            if absent_3w:
                priority = 'red_now'
            elif student.fee_warning == 'out':
                priority = 'red'
            elif absent or student.fee_warning == 'low':
                priority = 'yellow'
            else:
                priority = 'ok'
            vals = {
                'hours_n0': h.get(week.number, 0.0),
                'hours_n1': h.get(week.number - 1, 0.0),
                'hours_n2': h.get(week.number - 2, 0.0),
                'absent_streak': streak, 'absent': absent, 'absent_3w': absent_3w,
                'suggest_stop': streak >= stop_weeks,
                'session_count': sessions_n0[student.id],
                'last_session_date': student.last_session_date,
                'fee_warning': student.fee_warning, 'balance': student.balance,
                'remaining_blocks': student.remaining_blocks,
                'warning_sessions': warnings_n0[student.id], 'priority': priority,
            }
            alert = existing.pop(student.id, None)
            if alert:
                alert.write(vals)
            else:
                self.create(dict(vals, week_id=week.id, student_id=student.id))
        self.browse([a.id for a in existing.values()]).unlink()
        return self.search([('week_id', '=', week.id)])

    @api.model
    def _default_week(self):
        """Tuần chứa hôm nay; nếu không có thì tuần mới nhất đã bắt đầu."""
        today = fields.Date.context_today(self)
        week = self.env['edu.week'].search(
            [('date_from', '<=', today)], order='number desc', limit=1)
        return week

    def action_stop_student(self):
        self.mapped('student_id').action_stop()
        return True
