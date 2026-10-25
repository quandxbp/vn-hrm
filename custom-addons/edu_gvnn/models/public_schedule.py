from datetime import timedelta
import hashlib
import re
from urllib.parse import urlsplit, parse_qs

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..tools import normalize_name


class PublicSchedule(models.AbstractModel):
    _name = 'edu.public.schedule'
    _description = 'Thông tin lịch dạy công khai'

    @staticmethod
    def _drive_link(value):
        value = (value or '').strip()
        try:
            link = urlsplit(value)
            if (link.scheme in ('https', 'http') and link.hostname in ('drive.google.com', 'docs.google.com')
                    and not link.username and not link.password and link.port in (None, 80, 443)
                    and not any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)):
                return value
        except ValueError:
            pass
        return ''

    @api.model
    def _editor(self, token):
        if not isinstance(token, str) or len(token) != 43:
            return self.env['edu.teacher'].sudo().browse()
        return self.env['edu.teacher'].sudo().search([
            ('schedule_edit_token', '=', token), ('active', '=', True)], limit=1)

    @staticmethod
    def _attendance_version(session):
        roster = [(a.id, a.student_id.id, a.present) for a in session.attendee_ids.sorted('id')]
        return hashlib.sha256(repr(roster).encode()).hexdigest()

    @api.model
    def _save_attendance(self, token, session_id, absent_ids, original_attendance):
        teacher = self._editor(token)
        if not teacher:
            return 403, 'This editing link is invalid or no longer available.'
        try:
            session_id = int(session_id)
            if not 0 < session_id <= 2147483647:
                raise ValueError()
            if not isinstance(absent_ids, (list, tuple)) or len(absent_ids) > 100:
                raise ValueError()
            absent = {int(value) for value in absent_ids}
        except (ValueError, TypeError):
            return 400, 'Invalid attendance selection.'
        session = self.env['edu.session'].sudo().search([
            ('id', '=', session_id), ('teacher_id', '=', teacher.id)], limit=1)
        if not session:
            return 404, 'Lesson not found.'
        self.env.cr.execute('SELECT id FROM edu_session WHERE id = %s FOR UPDATE', [session.id])
        self.env.cr.execute('SELECT id FROM edu_session_attendee WHERE session_id = %s ORDER BY id FOR UPDATE', [session.id])
        session.invalidate_recordset(['teacher_id', 'paid', 'state', 'attendee_ids'])
        attendees = session.attendee_ids
        attendees.invalidate_recordset(['present', 'student_id'])
        if session.teacher_id.id != teacher.id:
            return 404, 'Lesson not found.'
        if session.paid or session.state == 'cancel':
            return 409, 'Attendance is locked for this lesson. Contact Kim Academy to make changes.'
        if not attendees or not absent.issubset(set(attendees.ids)):
            return 400, 'Select only students listed in this lesson.'
        if original_attendance != self._attendance_version(session):
            return 409, 'Attendance has changed since you opened this page. Reload and try again.'
        try:
            with self.env.cr.savepoint():
                for attendee in attendees:
                    present = attendee.id not in absent
                    if attendee.present != present:
                        attendee.write({'present': present})
        except UserError:
            return 409, 'Attendance cannot be changed right now. Contact Kim Academy.'
        return 200, ''

    @api.model
    def _save_recording(self, token, session_id, recording, original_recording):
        teacher = self._editor(token)
        if not teacher:
            return 403, 'This editing link is invalid or no longer available.'
        try:
            session_id = int(session_id)
            if not 0 < session_id <= 2147483647:
                raise ValueError()
        except (ValueError, TypeError):
            return 404, 'Lesson not found.'
        session = self.env['edu.session'].sudo().search([
            ('id', '=', session_id), ('teacher_id', '=', teacher.id)], limit=1)
        if not session:
            return 404, 'Lesson not found.'
        recording = (recording or '').strip()
        if len(recording) > 2048 or (recording and not self._drive_link(recording)):
            return 400, 'Enter a Google Drive link from drive.google.com or docs.google.com.'
        # Lock before checking the original value, so concurrent edits cannot overwrite each other.
        self.env.cr.execute('SELECT id FROM edu_session WHERE id = %s FOR UPDATE', [session.id])
        session.invalidate_recordset(['google_drive_url', 'teacher_id'])
        if session.teacher_id.id != teacher.id:
            return 404, 'Lesson not found.'
        if (session.google_drive_url or '') != (original_recording or ''):
            return 409, 'Recording has changed since you opened this page. Reload and try again.'
        if (session.google_drive_url or '') == recording:
            return 200, ''
        if session.youtube_url:
            return 409, 'Part 1 already has a YouTube video. Contact Kim Academy before changing its source.'
        if not recording and session.recording_part_ids:
            return 409, 'Remove additional parts before clearing Part 1.'
        try:
            with self.env.cr.savepoint():
                # Recording is metadata, allowed after payroll closure. All video job guards still apply.
                session.with_context(edu_payroll_internal=True).write({'google_drive_url': recording or False})
        except UserError:
            return 409, 'This recording cannot be changed right now. Contact Kim Academy to check its video upload or lesson status.'
        return 200, ''

    @staticmethod
    def _recording_version(session):
        return hashlib.sha256(repr(session._recording_parts()).encode()).hexdigest()

    @api.model
    def _save_recordings(self, token, session_id, recording, part_ids, part_urls, original_version):
        teacher = self._editor(token)
        if not teacher:
            return 403, 'This editing link is invalid or no longer available.'
        try:
            session_id = int(session_id)
            if not 0 < session_id <= 2147483647:
                raise ValueError()
            if len(part_ids) != len(part_urls) or len(part_urls) > 9:
                raise ValueError()
            ids = [int(value) if value else 0 for value in part_ids]
            if any(value < 0 for value in ids) or len([i for i in ids if i]) != len(set(i for i in ids if i)):
                raise ValueError()
        except (TypeError, ValueError):
            return 400, 'Invalid recording parts. A lesson supports up to 10 parts.'
        urls = [(value or '').strip() for value in [recording] + part_urls]
        if any(len(url) > 2048 or (url and not self._drive_link(url)) for url in urls):
            return 400, 'Enter valid Google Drive links for all parts.'
        if any(not url for url in urls[1:]) or (part_urls and not urls[0]):
            return 400, 'Enter a link for each part, or remove the empty part.'
        keys = []
        for url in filter(None, urls):
            parsed = urlsplit(url)
            match = re.search(r'/d/([^/]+)', parsed.path)
            keys.append(match.group(1) if match else parse_qs(parsed.query).get('id', [url])[0])
        if len(keys) != len(set(keys)):
            return 400, 'Each part must use a different Google Drive video.'
        session = self.env['edu.session'].sudo().search([
            ('id', '=', session_id), ('teacher_id', '=', teacher.id)], limit=1)
        if not session:
            return 404, 'Lesson not found.'
        self.env.cr.execute('SELECT id FROM edu_session WHERE id = %s FOR UPDATE', [session.id])
        self.env.cr.execute('SELECT id FROM edu_session_recording_part WHERE session_id = %s ORDER BY id FOR UPDATE', [session.id])
        session.invalidate_recordset(['teacher_id', 'google_drive_url', 'youtube_url', 'recording_part_ids'])
        parts = session.recording_part_ids
        parts.invalidate_recordset()
        if session.teacher_id.id != teacher.id:
            return 404, 'Lesson not found.'
        if not set(filter(None, ids)).issubset(set(parts.ids)):
            return 404, 'Recording part not found in this lesson.'
        if original_version != self._recording_version(session):
            return 409, 'Recordings have changed since you opened this page. Reload and try again.'
        try:
            with self.env.cr.savepoint():
                # Delete before clearing Part 1. All operations roll back if any part cannot be changed.
                number = max([1] + parts.mapped('number'))
                removed = parts.filtered(lambda p: p.id not in ids)
                removed.unlink()
                status, error = self._save_recording(token, session_id, urls[0], session.google_drive_url)
                if status != 200:
                    raise UserError(error)
                for part_id, url in zip(ids, urls[1:]):
                    if part_id:
                        part = parts.browse(part_id)
                        if part.google_drive_url != url:
                            part.write({'google_drive_url': url})
                    else:
                        number += 1
                        self.env['edu.session.recording.part'].sudo().create({
                            'session_id': session.id, 'number': number, 'google_drive_url': url})
        except UserError:
            return 409, 'No changes were saved. A part already has a YouTube video or upload history. Contact Kim Academy before replacing or removing it.'
        return 200, ''

    @staticmethod
    def _time(value):
        minutes = round(value * 60) % 1440
        return '%02d:%02d' % divmod(minutes, 60)

    @api.model
    def _get_values(self, teacher_name, week_number=None, editor=None):
        values = {'status': 200, 'error': '', 'teacher_name': '', 'teacher_query': '',
                  'week_label': '', 'date_range': '', 'week_options': [], 'selected_week': '', 'rows': [], 'edit_mode': False, 'form_action': '/weekly-schedule',
                  'edit_token': '', 'notice': '', 'save_error': ''}
        if (not isinstance(teacher_name, str) or not teacher_name.strip() or len(teacher_name) > 120
                or any(ord(char) < 32 for char in teacher_name)):
            return dict(values, status=404, error='Open your teaching schedule link, for example ?teacher=zahra.')
        # An exact normalized name prevents wildcard matching and never lists other teachers.
        teacher = self.env['edu.teacher'].sudo().search([
            ('name', '=', normalize_name(teacher_name)), ('active', '=', True)], limit=1)
        if not teacher:
            return dict(values, status=404, error='Teaching schedule not found.')
        values.update(teacher_name=teacher.name, teacher_query=teacher.name.casefold())
        if editor and editor.id == teacher.id:
            values.update(edit_mode=True, edit_token=editor.schedule_edit_token,
                          form_action='/weekly-schedule/edit/' + editor.schedule_edit_token)
        Week = self.env['edu.week'].sudo()
        today = fields.Date.context_today(self.with_context(tz='Asia/Ho_Chi_Minh'))
        if week_number not in (None, ''):
            try:
                number = int(week_number)
                if not 0 < number <= 2147483647 or str(number) != str(week_number):
                    raise ValueError()
            except (ValueError, TypeError):
                return dict(values, status=400, error='Invalid week number.')
            selected = Week.search([('number', '=', number)], limit=1)
            if not selected:
                return dict(values, status=404, error='Week not found.')
        else:
            selected = Week.search([('date_from', '<=', today), ('date_to', '>=', today)], limit=1)
        monday = today - timedelta(days=today.weekday())
        start, end = (selected.date_from, selected.date_to) if selected else (monday, monday + timedelta(days=6))
        values.update(week_label='Week %s' % selected.number if selected else 'Current week',
                      date_range='%s – %s' % (start.strftime('%d/%m/%Y'), end.strftime('%d/%m/%Y')),
                      selected_week=str(selected.number) if selected else '')
        Session = self.env['edu.session'].sudo()
        groups = Session.read_group([('teacher_id', '=', teacher.id), ('week_id', '!=', False)],
                                    ['week_id'], ['week_id'], orderby='week_id asc')
        week_ids = {group['week_id'][0] for group in groups if group['week_id']}
        if selected:
            week_ids.add(selected.id)
        values['week_options'] = [{'number': str(week.number), 'label': 'Week %s (%s – %s)' % (week.number, week.date_from.strftime('%d/%m/%Y'), week.date_to.strftime('%d/%m/%Y'))}
                                  for week in Week.search([('id', 'in', list(week_ids))], order='number desc')]
        domain = [('teacher_id', '=', teacher.id)]
        domain += [('week_id', '=', selected.id)] if selected else [('date', '>=', start), ('date', '<=', end)]
        for session in Session.search(domain, order='date, time_start, id'):
            students = [{'name': attendee.student_id.name, 'absent': not attendee.present}
                        for attendee in session.attendee_ids]
            if session.session_type == 'testing':
                students = [{'name': 'TESTING — ' + ' + '.join(session.class_ids.mapped('name')), 'absent': False}]
            if session.extra_participants:
                students.append({'name': session.extra_participants, 'absent': False})
            # Only plain, allowlisted values reach the public template: no sudo recordsets.
            values['rows'].append({
                'week': 'Week %s' % session.week_id.number if session.week_id else values['week_label'],
                'date': session.date.strftime('%d/%m/%Y'), 'weekday': session.weekday,
                'teacher': teacher.name,
                'time': '%s–%s' % (self._time(session.time_start), self._time(session.time_end))
                        if session.time_start or session.time_end else 'Time not set',
                'students': students, 'cancelled': session.state == 'cancel',
                'recording': self._drive_link(session.google_drive_url),
                'recordings': [{'number': part['number'], 'url': self._drive_link(part['drive'])}
                               for part in session._recording_parts() if self._drive_link(part['drive'])],
            })
            if values['edit_mode']:
                values['rows'][-1].update(
                    session_id=session.id, original_recording=session.google_drive_url or '',
                    recording_version=self._recording_version(session),
                    recording_parts=[{'id': p['id'], 'number': p['number'], 'url': p['drive']}
                                     for p in session._recording_parts()],
                    attendance_locked=session.paid or session.state == 'cancel',
                    extra_participants=session.extra_participants or '',
                    original_attendance=self._attendance_version(session),
                    attendees=[{'id': a.id, 'name': a.student_id.name, 'absent': not a.present}
                               for a in session.attendee_ids])
        return values
