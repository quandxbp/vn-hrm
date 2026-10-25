from odoo import http
from odoo.http import request
from markupsafe import Markup
from urllib.parse import urlencode


class PublicTeacherSchedule(http.Controller):
    def _save_json(self, status, error, session_id, kind):
        payload = {'success': status == 200, 'message': error}
        if status == 200:
            session = request.env['edu.session'].sudo().browse(int(session_id))
            if kind == 'attendance':
                payload.update(message='Attendance saved successfully.',
                               original_attendance=request.env['edu.public.schedule']._attendance_version(session))
            else:
                payload.update(message='Recording saved successfully.', recording=session.google_drive_url or '',
                               recording_version=request.env['edu.public.schedule']._recording_version(session),
                               recording_parts=[{'id': p['id'], 'number': p['number'], 'url': p['drive']}
                                                for p in session._recording_parts()])
        return request.make_json_response(payload, status=status, headers={
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer'})

    def _render(self, values):
        request.update_context(lang='en_US')
        response = request.render('edu_gvnn.public_weekly_schedule', dict(values, doctype=Markup('<!DOCTYPE html>')))
        response.status_code = values['status']
        response.headers.update({
            'Cache-Control': 'no-store',
            'X-Robots-Tag': 'noindex, nofollow',
            'Referrer-Policy': 'no-referrer',
            'X-Content-Type-Options': 'nosniff',
        })
        return response

    @http.route('/weekly-schedule', type='http', auth='public', methods=['GET'], sitemap=False)
    def weekly_schedule(self, teacher=None, week=None, **kwargs):
        return self._render(request.env['edu.public.schedule']._get_values(teacher, week))

    @http.route('/weekly-schedule/edit/<string:token>', type='http', auth='public', methods=['GET'], sitemap=False)
    def edit_schedule(self, token, week=None, saved=None, **kwargs):
        page = request.env['edu.public.schedule']
        teacher = page._editor(token)
        values = page._get_values(teacher.name if teacher else None, week, editor=teacher)
        if not teacher:
            values.update(status=403, error='This editing link is invalid or no longer available.')
        elif saved == '1':
            values['notice'] = 'Recording saved successfully.'
        elif saved == 'attendance':
            values['notice'] = 'Attendance saved successfully.'
        return self._render(values)

    @http.route('/weekly-schedule/attendance', type='http', auth='public', methods=['POST'], sitemap=False)
    def save_attendance(self, edit_token=None, session_id=None, original_attendance=None, week=None, **kwargs):
        page = request.env['edu.public.schedule']
        status, error = page._save_attendance(
            edit_token, session_id, request.httprequest.form.getlist('absent'), original_attendance)
        if request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._save_json(status, error, session_id, 'attendance')
        teacher = page._editor(edit_token)
        if status == 200:
            response = request.redirect('/weekly-schedule/edit/' + edit_token + '?' + urlencode({
                'week': week or '', 'saved': 'attendance'}), code=303)
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Referrer-Policy'] = 'no-referrer'
            return response
        values = page._get_values(teacher.name if teacher else None, week, editor=teacher)
        values.update(status=status, save_error=error)
        if not teacher:
            values['error'] = error
        return self._render(values)

    @http.route('/weekly-schedule/recording', type='http', auth='public', methods=['POST'], sitemap=False)
    def save_recording(self, edit_token=None, session_id=None, recording=None, original_recording=None, week=None, **kwargs):
        page = request.env['edu.public.schedule']
        form = request.httprequest.form
        if form.get('multipart') == '1':
            status, error = page._save_recordings(edit_token, session_id, recording,
                form.getlist('part_id'), form.getlist('part_url'), form.get('original_recordings'))
        else:
            status, error = page._save_recording(edit_token, session_id, recording, original_recording)
        if request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self._save_json(status, error, session_id, 'recording')
        teacher = page._editor(edit_token)
        if status == 200:
            response = request.redirect('/weekly-schedule/edit/' + edit_token + '?' + urlencode({'week': week or '', 'saved': '1'}), code=303)
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Referrer-Policy'] = 'no-referrer'
            return response
        values = page._get_values(teacher.name if teacher else None, week, editor=teacher)
        values.update(status=status, save_error=error)
        if not teacher:
            values['error'] = error
        return self._render(values)
