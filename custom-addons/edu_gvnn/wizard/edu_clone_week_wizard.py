from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class EduCloneWeekWizard(models.TransientModel):
    _name = 'edu.clone.week.wizard'
    _description = 'Sao chép lịch học theo tuần'

    source_week_id = fields.Many2one('edu.week', 'Tuần nguồn', required=True)
    target_week_id = fields.Many2one('edu.week', 'Tuần đã tạo', readonly=True)
    new_week_number = fields.Integer('Số tuần mới', compute='_compute_new_number', store=True, readonly=False)
    new_date_from = fields.Date('Ngày bắt đầu tuần mới', compute='_compute_new_start', store=True, readonly=False)
    new_date_to = fields.Date('Ngày kết thúc', compute='_compute_new_date_to')
    include_cancelled = fields.Boolean('Lấy cả lịch của buổi đã nghỉ', default=True,
        help='Buổi mới được tạo theo trạng thái mặc định Đã dạy, không giữ trạng thái Nghỉ của tuần cũ.')
    source_count = fields.Integer('Số buổi nguồn', compute='_compute_counts')
    result = fields.Text('Kết quả', readonly=True)
    completed = fields.Boolean(readonly=True)
    created_ids = fields.Many2many('edu.session', readonly=True)

    @api.model
    def default_get(self, names):
        vals = super().default_get(names)
        Week = self.env['edu.week']
        selected = self.env['edu.session'].browse(self.env.context.get('active_ids', [])).exists() \
            if self.env.context.get('active_model') == 'edu.session' else self.env['edu.session']
        sources = selected.mapped('week_id')
        latest_session = self.env['edu.session'].search([], order='date desc,id desc', limit=1)
        source = sources if len(sources) == 1 else (latest_session.week_id or Week.search([], order='date_to desc', limit=1))
        if source and 'source_week_id' in names:
            vals.setdefault('source_week_id', source.id)
        return vals

    @api.depends('source_week_id')
    def _compute_new_number(self):
        latest = self.env['edu.week'].search([], order='date_to desc', limit=1)
        for wizard in self:
            anchor = latest or wizard.source_week_id
            wizard.new_week_number = anchor.number + 1 if anchor else 1

    @api.depends('source_week_id')
    def _compute_new_start(self):
        latest = self.env['edu.week'].search([], order='date_to desc', limit=1)
        for wizard in self:
            anchor = latest or wizard.source_week_id
            wizard.new_date_from = anchor.date_to + timedelta(days=1) if anchor else fields.Date.context_today(wizard)

    @api.depends('new_date_from')
    def _compute_new_date_to(self):
        for wizard in self:
            wizard.new_date_to = wizard.new_date_from + timedelta(days=6) if wizard.new_date_from else False

    def _sessions(self, week, source=False):
        if not week:
            return self.env['edu.session']
        domain = [('date', '>=', week.date_from), ('date', '<=', week.date_to)]
        if source and not self.include_cancelled:
            domain.append(('state', '!=', 'cancel'))
        return self.env['edu.session'].search(domain, order='date,time_start,id')

    @api.depends('source_week_id', 'include_cancelled')
    def _compute_counts(self):
        for wizard in self:
            wizard.source_count = len(wizard._sessions(wizard.source_week_id, source=True))

    def _key(self, session, date):
        return (date, session.teacher_id.id, round(session.time_start * 60), round(session.time_end * 60),
                session.session_type, tuple(sorted(session.class_ids.ids)),
                tuple(sorted(session.attendee_ids.student_id.ids)))

    def action_clone(self):
        self.ensure_one()
        if not self.env.user.has_group('edu_gvnn.group_edu_manager'):
            raise UserError('Chỉ quản lý GVNN được tạo tuần mới từ lịch cũ.')
        self.env.cr.execute('SELECT id FROM edu_clone_week_wizard WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        if self.completed:
            return self.action_open_created()
        # The new week and all its lessons must either succeed together or leave no changes.
        with self.env.cr.savepoint():
            return self._clone_week()

    def _clone_week(self):
        source = self.source_week_id
        sessions = self._sessions(source, source=True)
        if not sessions:
            raise UserError('Tuần nguồn không có buổi học phù hợp để sao chép.')
        if self.new_week_number <= 0 or not self.new_date_from:
            raise UserError('Hãy nhập số tuần mới lớn hơn 0 và ngày bắt đầu.')
        self.env.cr.execute('SELECT pg_advisory_xact_lock(87422, 1)')
        Week = self.env['edu.week']
        if Week.search_count([('number', '=', self.new_week_number)]):
            raise UserError('Số tuần này đã tồn tại. Hãy nhập số tuần mới khác.')
        if Week.search_count([('date_from', '<=', self.new_date_to), ('date_to', '>=', self.new_date_from)]):
            raise UserError('Ngày của tuần mới bị trùng với một tuần đã có. Hãy chọn ngày khác.')
        target = Week.create({'number': self.new_week_number, 'date_from': self.new_date_from,
                              'date_to': self.new_date_to})
        if not source or not target or source.date_to >= target.date_from:
            raise UserError('Hãy chọn tuần nguồn trước tuần đích. Hai tuần phải khác nhau.')
        if (source.date_to - source.date_from).days > 6 or (target.date_to - target.date_from).days != 6:
            raise UserError('Tuần nguồn không được quá 7 ngày; tuần đích phải đủ 7 ngày để giữ đúng thứ.')
        Session = self.env['edu.session']
        # Serialize clone requests for the destination without locking or editing the historical week.
        self.env.cr.execute('SELECT id FROM edu_week WHERE id = %s FOR UPDATE', [target.id])
        existing = set()
        values, skipped = [], 0
        for session in sessions:
            date = target.date_from + timedelta(days=(session.date.weekday() - target.date_from.weekday()) % 7)
            key = self._key(session, date)
            if key in existing:
                skipped += 1
                continue
            Session._check_period_open(date)
            values.append({
                'date': date, 'teacher_id': session.teacher_id.id, 'session_type': session.session_type,
                'time_start': session.time_start, 'time_end': session.time_end,
                'class_ids': [fields.Command.set(session.class_ids.ids)],
                'extra_participants': session.extra_participants,
                'attendee_ids': [fields.Command.create({'student_id': attendee.student_id.id})
                                 for attendee in session.attendee_ids],
            })
            existing.add(key)
        created = Session.create(values) if values else Session
        self.write({'completed': True, 'target_week_id': target.id, 'created_ids': [fields.Command.set(created.ids)],
            'result': 'Đã tạo %s buổi từ tuần %s sang tuần %s; bỏ qua %s buổi trùng lịch. '
                      'Tuần nguồn được giữ nguyên.' % (
                          len(created), source.number, target.number, skipped)})
        return {'type': 'ir.actions.act_window', 'name': 'Kết quả sao chép lịch tuần',
                'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def action_open_created(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Lịch học vừa sao chép',
                'res_model': 'edu.session', 'view_mode': 'tree,form',
                'domain': [('id', 'in', self.created_ids.ids)]}
