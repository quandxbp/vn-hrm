import hashlib
import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.addons.edu_video.models.job import parse_drive_url


class SessionReviewLink(models.Model):
    _inherit = 'edu.session'

    ai_review_ids = fields.One2many('edu.session.review', 'session_id', 'Lịch sử nhận xét AI',
                                    groups='edu_gvnn.group_edu_manager')
    ai_review_id = fields.Many2one('edu.session.review', compute='_compute_ai_review', store=True,
                                   groups='edu_gvnn.group_edu_manager')
    ai_review_state = fields.Selection(related='ai_review_id.state', groups='edu_gvnn.group_edu_manager')
    ai_review_current = fields.Boolean(related='ai_review_id.source_current', groups='edu_gvnn.group_edu_manager')
    ai_review_summary = fields.Text(related='ai_review_id.summary', groups='edu_gvnn.group_edu_manager')
    ai_review_score = fields.Char(related='ai_review_id.score_display', groups='edu_gvnn.group_edu_manager')
    ai_review_time = fields.Char(related='ai_review_id.time_display', groups='edu_gvnn.group_edu_manager')
    ai_student_report = fields.Text(related='ai_review_id.student_report', groups='edu_gvnn.group_edu_manager')
    ai_student_alert_count = fields.Integer(related='ai_review_id.student_alert_count', groups='edu_gvnn.group_edu_manager')

    def _review_roster(self):
        self.ensure_one()
        rows = []
        for attendee in self.attendee_ids.sorted('id'):
            student = attendee.student_id
            aliases = list(dict.fromkeys(' '.join(name.split()) for name in
                (student.name_en or '', student.name_vi or '') if name.strip()))
            rows.append({'key': 'student_%s' % student.id,
                         'label': ' / '.join(aliases) or 'Học sinh #%s' % student.id, 'aliases': aliases})
        return rows

    def action_open_ai_review(self):
        self.ensure_one()
        self.ai_review_id._manager()
        return self.ai_review_id.get_formview_action()

    @api.depends('ai_review_ids', 'ai_review_ids.state')
    def _compute_ai_review(self):
        for session in self:
            session.ai_review_id = session.ai_review_ids.sorted('id', reverse=True)[:1]

    def _review_sources(self):
        self.ensure_one()
        return [part for part in self._recording_parts() if part['drive']]

    def _review_signature(self):
        return hashlib.sha256(json.dumps([(part['number'], part['drive']) for part in self._review_sources()],
                                        ensure_ascii=True).encode()).hexdigest()

    def _queue_ai_review(self, force=False):
        self.ensure_one()
        config = self.env.ref('edu_video.config_default').sudo()
        config._review_ready()
        sources = self._review_sources()
        if self.state == 'cancel' or not sources:
            raise UserError('Cần buổi học chưa nghỉ và có ít nhất một link Drive để phân tích.')
        if len(sources) > 10:
            raise UserError('Một báo cáo hỗ trợ tối đa 10 phần video.')
        # Serialize manual and automatic requests, including different users.
        self.env.cr.execute('SELECT id FROM edu_session WHERE id=%s FOR UPDATE', [self.id])
        signature = self._review_signature()
        Review = self.env['edu.session.review'].sudo()
        previous = Review.search([('session_id', '=', self.id), ('source_signature', '=', signature)], limit=1)
        roster = self._review_roster()
        planned = max(0, (self.time_end - self.time_start) * 60)
        if previous and (previous.state in ('queued', 'processing', 'analyzing') or
                not force and previous.state == 'done' and previous.prompt_version == '2.1'
                and (previous.roster_snapshot or []) == roster and previous.planned_minutes == planned):
            return previous
        Review.search([('session_id', '=', self.id), ('state', '=', 'queued'),
                       ('source_signature', '!=', signature)]).write({'state': 'cancelled', 'cleanup_pending': True})
        commands = []
        for part in sources:
            file_id, resource_key = parse_drive_url(part['drive'])
            commands.append(fields.Command.create({'number': part['number'], 'source_url': part['drive'],
                                                    'file_id': file_id, 'resource_key': resource_key}))
        return Review.create({'name': 'Nhận xét AI — %s' % self.display_name,
            'session_id': self.id, 'source_signature': signature, 'model_name': config.review_model,
            'execution_mode': config.review_execution,
            'requested_by': self.env.uid, 'part_ids': commands,
            'roster_snapshot': roster, 'planned_minutes': planned})

    def action_analyze_lesson(self):
        if not self.env.user.has_group('edu_gvnn.group_edu_manager'):
            raise AccessError('Chỉ quản lý GVNN được phân tích buổi học.')
        self.check_access_rights('write')
        self.check_access_rule('write')
        review = self._queue_ai_review(force=True)
        return {'type': 'ir.actions.act_window', 'res_model': 'edu.session.review',
                'res_id': review.id, 'view_mode': 'form', 'target': 'current'}

    def _auto_queue_ai_review(self):
        config = self.env.ref('edu_video.config_default').sudo()
        if config.review_enabled and config.review_auto and config.review_api_key:
            for session in self.filtered(lambda rec: rec.state != 'cancel' and rec._review_sources()):
                # A bad/missing source must not prevent attendance edits or YouTube upload.
                try:
                    with self.env.cr.savepoint():
                        session._queue_ai_review()
                except UserError:
                    pass

    @api.model_create_multi
    def create(self, vals_list):
        sessions = super().create(vals_list)
        sessions._auto_queue_ai_review()
        return sessions

    def write(self, vals):
        result = super().write(vals)
        if 'google_drive_url' in vals or 'recording_part_ids' in vals:
            self._auto_queue_ai_review()
        return result


class RecordingReviewLink(models.Model):
    _inherit = 'edu.session.recording.part'

    @api.model_create_multi
    def create(self, vals_list):
        parts = super().create(vals_list)
        parts.session_id._auto_queue_ai_review()
        return parts

    def write(self, vals):
        result = super().write(vals)
        if 'google_drive_url' in vals or 'number' in vals:
            self.session_id._auto_queue_ai_review()
        return result

    def unlink(self):
        sessions = self.session_id
        result = super().unlink()
        sessions._auto_queue_ai_review()
        return result
