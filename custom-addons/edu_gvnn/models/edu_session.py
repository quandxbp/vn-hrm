# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup
from ..tools import youtube_recording_url

WEEKDAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']


class EduSession(models.Model):
    _name = 'edu.session'
    _description = 'Buổi học'
    _inherit = ['mail.thread']
    _order = 'date desc, time_start desc, id desc'

    date = fields.Date('Ngày', required=True, default=fields.Date.context_today, index=True, tracking=True)
    week_id = fields.Many2one(
        'edu.week', 'Tuần', compute='_compute_week', store=True, readonly=False, index=True, tracking=True)
    weekday = fields.Selection(
        [(d, d) for d in WEEKDAYS], string='Thứ', compute='_compute_weekday', store=True)
    session_type = fields.Selection(
        [('lesson', 'Buổi học'), ('testing', 'Buổi testing')],
        string='Loại buổi', required=True, default='lesson', index=True, tracking=True)
    teacher_id = fields.Many2one('edu.teacher', 'Giáo viên', required=True, index=True, tracking=True)
    class_ids = fields.Many2many(
        'edu.class', 'edu_session_class_rel', 'session_id', 'class_id', 'Lớp', tracking=True)
    time_start = fields.Float('Giờ bắt đầu', tracking=True)
    time_end = fields.Float('Giờ kết thúc', tracking=True)
    minutes = fields.Float('Phút', compute='_compute_minutes', store=True, readonly=False, tracking=True)
    student_hours = fields.Float(
        'Giờ tính cho HV', compute='_compute_hours', store=True, readonly=False, tracking=True)
    teacher_hours = fields.Float(
        'Giờ tính cho GV', compute='_compute_hours', store=True, readonly=False, tracking=True)
    state = fields.Selection(
        [('done', 'Đã dạy'), ('cancel', 'Nghỉ buổi học')],
        string='Trạng thái', required=True, default='done', index=True, tracking=True)
    attendee_ids = fields.One2many('edu.session.attendee', 'session_id', 'Học viên')
    student_names = fields.Char('Danh sách học viên', compute='_compute_student_names')
    student_badge_data = fields.Json('Thông tin hiển thị học viên', compute='_compute_student_badge_data')

    @api.depends('attendee_ids.student_id.name_vi', 'attendee_ids.student_id.name_en', 'attendee_ids.present')
    def _compute_student_badge_data(self):
        for session in self:
            session.student_badge_data = [{
                'id': attendee.student_id.id,
                'name': attendee.student_id.name_vi or '',
                'english': attendee.student_id.name_en or '',
                'present': attendee.present,
            } for attendee in session.attendee_ids]
    completion_note = fields.Char('Hoàn thành / ghi chú nhanh', tracking=True)
    note = fields.Text('Ghi chú', tracking=True)
    google_drive_url = fields.Char(
        'Link video Google Drive', copy=False, tracking=True,
        help='Link video gốc do giáo viên gửi sau buổi học.')
    youtube_url = fields.Char(
        'Link video YouTube', copy=False, tracking=True,
        help='Link video buổi học sau khi được đăng lên YouTube.')
    recording_part_ids = fields.One2many(
        'edu.session.recording.part', 'session_id', 'Các đoạn video bổ sung', copy=False)

    def _recording_parts(self):
        self.ensure_one()
        return [{'id': 0, 'number': 1, 'drive': self.google_drive_url or '', 'youtube': self.youtube_url or ''}] + [
            {'id': p.id, 'number': p.number, 'drive': p.google_drive_url or '', 'youtube': p.youtube_url or ''}
            for p in self.recording_part_ids.sorted('number')]
    # Retained for historical Excel compatibility; current UI uses the Video tab.
    recording_url = fields.Char('Recording (Excel cũ)', tracking=True,
        help='Dữ liệu tương thích Excel cũ. Dùng Link video Google Drive / YouTube cho buổi học mới.')
    video_posted = fields.Boolean('Đã đăng video (Excel cũ)', tracking=True,
        help='Dấu đánh đăng video trong Excel cũ; không phải trạng thái upload YouTube hiện tại.')
    extra_participants = fields.Char('Người tham gia khác', tracking=True)
    paid = fields.Boolean('Đã chốt lương', copy=False, readonly=True, tracking=True)
    period_id = fields.Many2one(
        'edu.payroll.period', 'Kỳ lương', compute='_compute_period', groups='edu_gvnn.group_edu_manager')
    locked = fields.Boolean('Tháng đã chốt', compute='_compute_period')
    import_key = fields.Char('Khoá import', copy=False, index=True)

    _sql_constraints = [
        ('import_key_uniq', 'unique(import_key)', 'Buổi học này đã được import.'),
    ]

    def _log_related_change(self, title, before=None, after=None):
        """Keep attendance and recording edits in their session's history."""
        self.ensure_one()
        if self.env.context.get('tracking_disable') or self.env.context.get('mail_notrack'):
            return
        before, after = before or {}, after or {}
        lines = [
            Markup('<li><strong>%s</strong>: %s → %s</li>') % (
                label, before.get(label, '—'), after.get(label, '—'))
            for label in dict.fromkeys([*before, *after])
            if before.get(label) != after.get(label)
        ]
        if lines:
            self.check_access_rights('write')
            self.check_access_rule('write')
            self._message_log(
                body=Markup('<p>%s</p><ul>%s</ul>') % (title, Markup('').join(lines)),
            )

    @api.model
    def _migrate_legacy_recordings(self):
        self.flush_model(['youtube_url', 'recording_url'])
        self.env.cr.execute("""
            SELECT id, recording_url FROM edu_session
            WHERE COALESCE(youtube_url, '') = '' AND COALESCE(recording_url, '') <> ''
        """)
        count = 0
        for session_id, recording in self.env.cr.fetchall():
            url = youtube_recording_url(recording)
            if url:
                # Metadata only: retain legacy values, bypass payroll writes and any upload hooks.
                self.env.cr.execute("""UPDATE edu_session SET youtube_url = %s
                    WHERE id = %s AND COALESCE(youtube_url, '') = ''""", [url, session_id])
                count += self.env.cr.rowcount
        self.invalidate_model(['youtube_url'])
        return count
    teacher_rate = fields.Float(
        'Đơn giá GV (đ/giờ)', digits=(16, 0), copy=False, tracking=True, groups='edu_gvnn.group_edu_manager')
    paid_hours = fields.Float('Giờ tính lương', compute='_compute_paid_hours', store=True, tracking=True)
    teacher_amount = fields.Float(
        'Lương buổi (đ)', digits=(16, 2), compute='_compute_teacher_amount', store=True,
        groups='edu_gvnn.group_edu_manager', tracking=True)
    warning = fields.Selection(
        [('ok', 'OK'), ('zero_hours', 'Giờ dạy = 0'), ('no_rate', 'Chưa có đơn giá'),
         ('duplicate', 'Trùng buổi'), ('no_student', 'Thiếu học viên')],
        string='Cảnh báo', compute='_compute_warning', store=True, index=True)

    @api.depends('date')
    def _compute_week(self):
        Week = self.env['edu.week']
        for rec in self:
            rec.week_id = Week._get_week(rec.date) if rec.date else False

    @api.depends('date', 'paid')
    def _compute_period(self):
        Period = self.env['edu.payroll.period'].sudo()
        for rec in self:
            period = Period.search([('date_from', '<=', rec.date), ('date_to', '>=', rec.date)], limit=1) \
                if rec.date else Period
            rec.period_id = period
            rec.locked = bool(period) and period.state == 'locked'

    @api.depends('date')
    def _compute_weekday(self):
        for rec in self:
            rec.weekday = WEEKDAYS[rec.date.weekday()] if rec.date else False

    @api.depends('time_start', 'time_end')
    def _compute_minutes(self):
        for rec in self:
            diff = ((rec.time_end - rec.time_start) * 60) % 1440 if (rec.time_start or rec.time_end) else 0
            rec.minutes = round(diff, 2) if diff > 0 else 30.0

    @api.depends('minutes')
    def _compute_hours(self):
        for rec in self:
            rec.student_hours = rec.teacher_hours = rec.minutes / 60.0

    @api.depends('attendee_ids.student_id', 'attendee_ids.present')
    def _compute_student_names(self):
        for rec in self:
            rec.student_names = ', '.join(
                a.student_id.name + ('' if a.present else ' (nghỉ)') for a in rec.attendee_ids)

    @api.depends('state', 'session_type', 'teacher_hours', 'attendee_ids.present')
    def _compute_paid_hours(self):
        for rec in self:
            if rec.state != 'done':
                rec.paid_hours = 0.0
            elif rec.session_type == 'testing' or any(rec.attendee_ids.mapped('present')):
                rec.paid_hours = rec.teacher_hours
            else:
                rec.paid_hours = 0.0

    @api.depends('paid_hours', 'teacher_rate')
    def _compute_teacher_amount(self):
        for rec in self:
            rec.teacher_amount = rec.paid_hours * rec.teacher_rate

    @api.depends('state', 'session_type', 'date', 'teacher_id', 'time_start', 'time_end',
                 'teacher_hours', 'teacher_rate', 'attendee_ids')
    def _compute_warning(self):
        for rec in self:
            rid = rec._origin.id
            if rec.state == 'cancel':
                rec.warning = 'ok'
            elif rec.teacher_hours <= 0:
                rec.warning = 'zero_hours'
            elif not rec.teacher_rate:
                rec.warning = 'no_rate'
            elif (rec.time_start or rec.time_end) and self.search_count(
                    [('date', '=', rec.date), ('teacher_id', '=', rec.teacher_id.id),
                     ('time_start', '=', rec.time_start), ('state', '=', 'done')]
                    + ([('id', '<', rid)] if rid else [])):
                rec.warning = 'duplicate'
            elif rec.session_type == 'lesson' and not rec.attendee_ids:
                rec.warning = 'no_student'
            else:
                rec.warning = 'ok'

    @api.depends('date', 'teacher_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (
                rec.date.strftime('%d/%m/%Y') if rec.date else '', rec.teacher_id.name or '')

    @api.constrains('session_type', 'attendee_ids', 'class_ids')
    def _check_session_type(self):
        for rec in self:
            if rec.session_type == 'lesson' and len(rec.attendee_ids) > 2:
                raise ValidationError('Buổi học thường chỉ có tối đa 2 học viên.')
            if rec.session_type == 'testing':
                if rec.attendee_ids:
                    raise ValidationError('Buổi testing không nhập học viên, chỉ chọn lớp được test.')
                if not rec.class_ids:
                    raise ValidationError('Buổi testing cần chọn lớp được test.')

    @api.onchange('time_start')
    def _onchange_time_start(self):
        if self.time_start and not self.time_end:
            self.time_end = (self.time_start + (self.minutes or 30) / 60.0) % 24

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_period_open(vals.get('date') or fields.Date.context_today(self))
        sessions = super().create(vals_list)
        for session, vals in zip(sessions, vals_list):
            if 'teacher_rate' not in vals:
                session._update_teacher_rate()
        return sessions

    def write(self, vals):
        if not self.env.context.get('edu_payroll_internal'):
            self._check_not_locked()
            if vals.get('date'):
                self._check_period_open(vals['date'])
        res = super().write(vals)
        if ('teacher_id' in vals or 'date' in vals) and 'teacher_rate' not in vals:
            self.filtered(lambda s: not s.paid)._update_teacher_rate()
        return res

    def unlink(self):
        self._check_not_locked()
        return super().unlink()

    def _check_not_locked(self):
        if any(self.mapped('paid')):
            raise UserError('Buổi học thuộc kỳ lương đã chốt, không thể sửa. Admin có thể mở khoá kỳ lương.')

    @api.model
    def _check_period_open(self, date):
        if self.env['edu.payroll.period'].sudo().search_count([
                ('state', '=', 'locked'), ('date_from', '<=', date), ('date_to', '>=', date)]):
            raise UserError('Tháng của ngày %s đã chốt lương, không thêm hoặc chuyển buổi học vào tháng này.' % date)

    def _update_teacher_rate(self):
        """Lấy đơn giá của GV tại ngày dạy. Buổi đã trả lương giữ nguyên đơn giá đã lưu."""
        for rec in self.filtered(lambda s: not s.paid):
            rate = rec.teacher_id._get_rate(rec.date) if rec.teacher_id and rec.date else 0.0
            if rec.sudo().teacher_rate != rate:
                rec.sudo().write({'teacher_rate': rate})

    @api.model
    def _recompute_rates(self, teacher, date_from):
        """Tính lại đơn giá cho các buổi chưa trả lương của GV từ `date_from`, khi lịch sử đơn giá đổi."""
        self.sudo().search([
            ('teacher_id', '=', teacher.id), ('date', '>=', date_from), ('paid', '=', False),
        ])._update_teacher_rate()

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_restore(self):
        self.write({'state': 'done'})
