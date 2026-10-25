from odoo import api, fields, models
from odoo.exceptions import UserError
from .job import JOB_STATES


class EduSession(models.Model):
    _inherit = 'edu.session'

    video_job_ids = fields.One2many('edu.video.job', 'session_id', 'Lịch sử upload video', groups='edu_gvnn.group_edu_manager')
    video_state = fields.Selection(JOB_STATES, compute='_compute_latest_video_job', string='Video YouTube', groups='edu_gvnn.group_edu_manager')

    @api.depends('video_job_ids', 'video_job_ids.state', 'google_drive_url', 'youtube_url',
                 'recording_part_ids.google_drive_url', 'recording_part_ids.youtube_url')
    def _compute_latest_video_job(self):
        for session in self:
            jobs = session.video_job_ids.filtered(
                lambda job: job.source_url == job._recording_target().google_drive_url)
            states = {'done' if job._recording_target().youtube_url else job.state for job in jobs}
            session.video_state = next((state for state in (
                'uncertain', 'failed', 'uploading', 'downloading', 'queued', 'cancelled', 'done')
                if state in states), False)

    def action_upload_youtube(self):
        if not self.env.user.has_group('edu_gvnn.group_edu_manager'):
            raise UserError('Chỉ quản lý GVNN được yêu cầu upload video.')
        for session in self:
            session.check_access_rights('write')
            session.check_access_rule('write')
            session._enqueue_video()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': 'Video YouTube', 'message': 'Đã xếp hàng. Video sẽ được xử lý nền khi cấu hình cho phép.',
            'type': 'success', 'sticky': False}}

    video_upload_pending = fields.Boolean(compute='_compute_video_upload_pending', groups='edu_gvnn.group_edu_manager')

    @api.depends('google_drive_url', 'youtube_url', 'recording_part_ids.google_drive_url', 'recording_part_ids.youtube_url')
    def _compute_video_upload_pending(self):
        for session in self:
            session.video_upload_pending = any(p['drive'] and not p['youtube'] for p in session._recording_parts())

    def _enqueue_video(self, target=None):
        self.ensure_one()
        if self.state == 'cancel':
            raise UserError('Cancelled lessons cannot be queued.')
        from .job import parse_drive_url
        self.env.cr.execute('SELECT id FROM edu_session WHERE id = %s FOR UPDATE', [self.id])
        Job = self.env['edu.video.job'].sudo()
        sources = [target] if target is not None else [self] + list(self.recording_part_ids)
        jobs = Job.browse()
        for source in sources:
            if not source.google_drive_url or source.youtube_url:
                continue
            file_id, resource_key = parse_drive_url(source.google_drive_url)
            part_id = source.id if source._name == 'edu.session.recording.part' else False
            existing = Job.search([('session_id', '=', self.id), ('file_id', '=', file_id)], limit=1)
            if existing:
                if existing.recording_part_id.id != part_id or existing.state in ('failed', 'cancelled', 'uncertain'):
                    raise UserError('This video already has upload history. Check its existing request before retrying.')
                jobs |= existing
            else:
                jobs |= Job.create({'session_id': self.id, 'recording_part_id': part_id,
                    'file_id': file_id, 'resource_key': resource_key, 'source_url': source.google_drive_url})
        if not jobs:
            raise UserError('No recording parts are waiting for YouTube upload.')
        return jobs

    @api.model_create_multi
    def create(self, vals_list):
        sessions = super().create(vals_list)
        config = self.env.ref('edu_video.config_default').sudo()
        if config.auto_upload:
            for session in sessions.filtered(lambda s: s.google_drive_url and not s.youtube_url and s.state != 'cancel'):
                session._enqueue_video()
        return sessions

    def write(self, vals):
        if 'google_drive_url' in vals:
            for session in self:
                if vals['google_drive_url'] != session.google_drive_url and self.env['edu.video.job'].sudo().search_count([
                        ('session_id', '=', session.id), ('state', 'in', ['queued', 'downloading', 'uploading', 'failed', 'uncertain'])]):
                    raise UserError('Hãy hủy/kiểm tra yêu cầu video hiện tại trước khi thay link Drive.')
        result = super().write(vals)
        config = self.env.ref('edu_video.config_default').sudo()
        if vals.get('google_drive_url') and config.auto_upload:
            for session in self.filtered(lambda s: not s.youtube_url and s.state != 'cancel'):
                session._enqueue_video(target=session)
        return result


class RecordingPart(models.Model):
    _inherit = 'edu.session.recording.part'

    def _check_video_history(self):
        super()._check_video_history()
        if self.env['edu.video.job'].sudo().search_count([('recording_part_id', 'in', self.ids)]):
            raise UserError('This part has upload history. Keep its source link and contact the manager.')

    @api.model_create_multi
    def create(self, vals_list):
        parts = super().create(vals_list)
        if self.env.ref('edu_video.config_default').sudo().auto_upload:
            for part in parts.filtered(lambda p: not p.youtube_url and p.session_id.state != 'cancel'):
                part.session_id._enqueue_video(target=part)
        return parts

    def write(self, vals):
        result = super().write(vals)
        if vals.get('google_drive_url') and self.env.ref('edu_video.config_default').sudo().auto_upload:
            for part in self.filtered(lambda p: not p.youtube_url and p.session_id.state != 'cancel'):
                part.session_id._enqueue_video(target=part)
        return result
