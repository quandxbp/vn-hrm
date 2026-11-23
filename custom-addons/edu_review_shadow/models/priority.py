"""Kim Worker as the primary AI review provider (edu_review_shadow.prefer_worker_since is set).

- Drive changes no longer auto-queue Gemini: the worker cron picks every taught session.
- 'Phân tích' on a taught session without a finished report goes to the worker, ahead of the queue.
- 'Phân tích ngay' (explicit Gemini model) and re-analysis of a finished report stay on Gemini.
"""
from odoo import fields, models
from odoo.exceptions import AccessError, UserError

from .shadow import ACTIVE

STAGES = {'asr': 'nhận dạng giọng nói', 'frames': 'đọc khung hình', 'synthesis': 'viết nhận xét',
          'queued': 'chờ worker', 'receiving': 'nhận video'}


class SessionWorkerPriority(models.Model):
    _inherit = 'edu.session'

    ai_worker_status = fields.Char('Kim Worker', compute='_compute_ai_worker_status', compute_sudo=True,
                                   groups='edu_gvnn.group_edu_manager')

    def _compute_ai_worker_status(self):
        Shadow = self.env['edu.session.review.shadow'].sudo()
        rows = Shadow.search([('mode', '=', 'official'), ('session_id', 'in', self.ids)], order='id desc') if self.ids else Shadow
        for session in self:
            row = rows.filtered(lambda r: r.session_id == session)[:1]
            status = False
            if row.state == 'upload':
                queue = Shadow.search([('state', '=', 'upload')]).sorted(Shadow._run_order)
                ahead = list(queue).index(row) + Shadow.search_count([('state', '=', 'waiting')])
                status = 'Kim Worker: đang chờ%s (còn %s buổi phía trước).' % (' — ưu tiên' if row.priority else '', ahead)
            elif row.state == 'waiting':
                status = 'Kim Worker đang phân tích: %s, %s%%.' % (
                    STAGES.get(row.worker_stage, row.worker_stage or 'đang xử lý'), round((row.worker_progress or 0) * 100))
            elif row.state == 'done' and (row.error or '').startswith('publish_wait'):
                status = 'Kim Worker đã xong; chờ lượt Gemini đang mở của buổi này kết thúc rồi mới lưu báo cáo.'
            elif row.state == 'failed' and not session.ai_review_done:
                status = 'Kim Worker lỗi (%s).%s' % (row.error or 'không rõ',
                    ' Đã chuyển sang Gemini.' if row.fallback_note == 'gemini_queued' else '')
            session.ai_worker_status = status

    def _auto_queue_ai_review(self):
        if self.env['edu.session.review.shadow'].sudo()._prefer_since():
            return  # the worker cron takes taught sessions; Gemini is only the fallback
        return super()._auto_queue_ai_review()

    def action_analyze_lesson(self):
        self.ensure_one()
        Shadow = self.env['edu.session.review.shadow'].sudo()
        if not Shadow._prefer_since() or self.state != 'done' or self.sudo().ai_review_done:
            return super().action_analyze_lesson()
        if not self.env.user.has_group('edu_gvnn.group_edu_manager'):
            raise AccessError('Chỉ quản lý GVNN được phân tích buổi học.')
        self.check_access_rights('write')
        self.check_access_rule('write')
        try:
            Shadow._ready()
        except UserError:
            return super().action_analyze_lesson()
        self._check_week_unlocked()
        sources = self._review_sources()
        if not sources:
            raise UserError('Cần buổi học chưa nghỉ và có ít nhất một link Drive để phân tích.')
        if len(sources) > 10:
            raise UserError('Một báo cáo hỗ trợ tối đa 10 phần video.')
        row = Shadow.search([('job_key', '=', Shadow._official_key(self))], limit=1)
        waiting_publish = row.state == 'done' and (row.error or '').startswith('publish_wait')
        if row and row.state not in ('upload', 'waiting') and not waiting_publish:
            return super().action_analyze_lesson()   # the worker already ended this video (failed/unusable): Gemini
        if not row:
            if Shadow._gemini_split(self)[0]:
                raise UserError('Buổi học đang có lượt Gemini đang chạy. Hãy chờ lượt đó kết thúc.')
            row = Shadow._queue_official(self, priority=True)
            if not row:
                raise UserError('Worker AI đang bận chuyển hàng đợi, hãy thử lại sau vài phút.')
        elif row.state == 'upload' and not row.priority:
            row.priority = True
        self.invalidate_recordset(['ai_worker_status'])
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'type': 'info', 'title': 'Kim Worker',
            'message': self.ai_worker_status or 'Đã gửi buổi học cho Kim Worker.',
            'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}}}
