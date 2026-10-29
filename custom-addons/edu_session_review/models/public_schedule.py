from odoo import api, models


class TeacherScheduleReview(models.AbstractModel):
    _inherit = 'edu.public.schedule'

    @api.model
    def _get_values(self, teacher_name, week_number=None, editor=None):
        values = super()._get_values(teacher_name, week_number, editor=editor)
        values['review_enabled'] = bool(values['edit_mode'])
        return values

    @api.model
    def _teacher_session_review(self, token, session_id):
        teacher = self._editor(token)
        if not teacher:
            return 403, {'message': 'This private teacher link is invalid or no longer available.'}
        try:
            if isinstance(session_id, bool):
                raise ValueError()
            session_id = int(session_id)
            if not 0 < session_id <= 2147483647:
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            return 404, {'message': 'Lesson not found.'}
        session = self.env['edu.session'].sudo().search([
            ('id', '=', session_id), ('teacher_id', '=', teacher.id)], limit=1)
        if not session:
            return 404, {'message': 'Lesson not found.'}
        payload = {'lesson': {
            'teacher': teacher.name, 'date': session.date.strftime('%d/%m/%Y'),
            'week': session.week_id.number or None,
            'time': '%s–%s' % (self._time(session.time_start), self._time(session.time_end)),
        }, 'state': 'missing'}
        review = self.env['edu.session.review'].sudo().search([
            ('session_id', '=', session.id)], order='id desc', limit=1)
        if not review:
            return 200, payload
        payload['state'] = review.state
        if review.state != 'done':
            # Errors can contain internal provider/configuration details. Keep them in the backend.
            return 200, payload
        text_fields = ('summary', 'lesson_content', 'strengths', 'improvements', 'score_details',
                       'interaction_comment', 'timing_note', 'timing_details', 'quality_note',
                       'teaching_started_at', 'time_display', 'score_display', 'ratio_display')
        report = {name: review[name] or '' for name in text_fields}
        report.update(
            sufficient_data=review.sufficient_data, score_available=review.score_available,
            score_total=review.score_total if review.score_available else None,
            interaction_level=review.interaction_level or '',
            completed_at=review.finished_at.isoformat() + 'Z' if review.finished_at else '',
            scores=[{'label': label, 'score': review[field], 'maximum': 2.5}
                    for field, label in [('score_content', 'Content'), ('score_instruction', 'Instruction'),
                                         ('score_interaction', 'Interaction'), ('score_management', 'Organisation')]]
                   if review.score_available else [],
            sources=[{'number': part.number, 'duration_seconds': part.duration,
                      'url': self._drive_link(part.source_url)} for part in review.part_ids],
        )
        payload.update(stale=not review.source_current, report=report)
        return 200, payload
