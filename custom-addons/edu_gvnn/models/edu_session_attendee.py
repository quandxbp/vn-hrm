# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..tools import get_param


class EduSessionAttendee(models.Model):
    _name = 'edu.session.attendee'
    _description = 'Học viên trong buổi học'
    _order = 'session_id, id'

    session_id = fields.Many2one(
        'edu.session', 'Buổi học', required=True, ondelete='cascade', index=True)
    student_id = fields.Many2one('edu.student', 'Học viên', required=True, index=True)
    present = fields.Boolean('Có mặt', default=True)
    score = fields.Integer('Điểm')
    block_price = fields.Float(
        'Đơn giá/buổi (đ)', digits=(16, 0),
        default=lambda self: get_param(self.env, 'block_price', 100000.0))
    charge_hours = fields.Float('Giờ trừ học phí', compute='_compute_charge', store=True)
    blocks = fields.Float('Số buổi trừ', compute='_compute_charge', store=True)
    charge_amount = fields.Float('Tiền trừ (đ)', digits=(16, 2), compute='_compute_charge', store=True)

    date = fields.Date(related='session_id.date', store=True, index=True)
    week_id = fields.Many2one(related='session_id.week_id', store=True)
    teacher_id = fields.Many2one(related='session_id.teacher_id', store=True)
    session_state = fields.Selection(related='session_id.state', store=True)
    session_type = fields.Selection(related='session_id.session_type', store=True)

    _sql_constraints = [
        ('session_student_uniq', 'unique(session_id, student_id)',
         'Học viên đã có trong buổi học này.'),
    ]

    @api.depends('present', 'block_price', 'session_id.state', 'session_id.session_type',
                 'session_id.student_hours')
    def _compute_charge(self):
        block_minutes = get_param(self.env, 'block_minutes', 30.0) or 30.0
        for rec in self:
            session = rec.session_id
            charged = rec.present and session.state == 'done' and session.session_type == 'lesson'
            rec.charge_hours = session.student_hours if charged else 0.0
            rec.blocks = rec.charge_hours * 60.0 / block_minutes
            rec.charge_amount = rec.blocks * rec.block_price

    def action_toggle_present(self):
        for rec in self:
            rec.present = not rec.present

    def _check_session_unlocked(self):
        if any(self.mapped('session_id.paid')):
            raise UserError('Buổi học thuộc kỳ lương đã chốt, không thể sửa học viên trong buổi.')

    def _change_snapshot(self):
        self.ensure_one()
        return {
            'Học viên': self.student_id.display_name,
            'Điểm danh': 'Có mặt' if self.present else 'Nghỉ',
            'Điểm': str(self.score),
            'Đơn giá/buổi (đ)': '%g' % self.block_price,
        }

    @api.model_create_multi
    def create(self, vals_list):
        sessions = self.env['edu.session'].browse([v['session_id'] for v in vals_list if v.get('session_id')])
        if any(sessions.mapped('paid')):
            raise UserError('Buổi học thuộc kỳ lương đã chốt, không thể thêm học viên vào buổi.')
        attendees = super().create(vals_list)
        for attendee in attendees:
            attendee.session_id._log_related_change('Thêm học viên', after=attendee._change_snapshot())
        return attendees

    def write(self, vals):
        self._check_session_unlocked()
        previous = {rec.id: (rec.session_id, rec._change_snapshot()) for rec in self}
        result = super().write(vals)
        for rec in self:
            session, before = previous[rec.id]
            after = rec._change_snapshot()
            if session != rec.session_id:
                session._log_related_change('Xóa học viên khỏi buổi', before=before)
                rec.session_id._log_related_change('Thêm học viên', after=after)
            else:
                session._log_related_change('Cập nhật học viên: %s' % rec.student_id.display_name, before, after)
        return result

    def unlink(self):
        self._check_session_unlocked()
        previous = [(rec.session_id, rec._change_snapshot()) for rec in self]
        result = super().unlink()
        for session, before in previous:
            session._log_related_change('Xóa học viên khỏi buổi', before=before)
        return result
