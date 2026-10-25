from datetime import date
from unittest.mock import patch
from lxml import html

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPublicSchedule(TransactionCase):
    def setUp(self):
        super().setUp()
        self.week = self.env['edu.week'].create({
            'number': 99875, 'date_from': '2041-01-07', 'date_to': '2041-01-13'})
        self.teacher = self.env['edu.teacher'].create({'name': 'Public Zahra'})
        self.other = self.env['edu.teacher'].create({'name': 'Public Other Teacher'})
        self.student = self.env['edu.student'].create({'name_vi': 'Public Student', 'name_en': 'Alex'})
        self.session = self.env['edu.session'].create({
            'date': '2041-01-08', 'teacher_id': self.teacher.id, 'time_start': 17.5, 'time_end': 18,
            'google_drive_url': 'https://drive.google.com/file/d/public_test_video/view',
            'youtube_url': 'https://youtu.be/not_public_recording', 'note': 'PRIVATE_NOTE_SENTINEL',
            'teacher_rate': 123456,
            'attendee_ids': [(0, 0, {'student_id': self.student.id})],
        })
        self.env['edu.session'].create({
            'date': '2041-01-08', 'teacher_id': self.other.id, 'note': 'OTHER_TEACHER_SENTINEL'})
        self.public = self.env.ref('base.public_user')
        self.page = self.env['edu.public.schedule'].with_user(self.public)

    def values(self, **kwargs):
        return self.page._get_values('public zahra', str(self.week.number), **kwargs)

    def test_public_projection_is_teacher_scoped_and_allowlisted(self):
        data = self.values()
        self.assertEqual(data['status'], 200)
        self.assertEqual(len(data['rows']), 1)
        row = data['rows'][0]
        self.assertEqual(set(row), {'week', 'date', 'weekday', 'teacher', 'time', 'students', 'cancelled', 'recording', 'recordings'})
        self.assertEqual(row['time'], '17:30–18:00')
        self.assertEqual(row['recording'], self.session.google_drive_url)
        self.assertEqual(row['students'][0]['name'], self.student.name)
        self.assertNotIn('PRIVATE_NOTE_SENTINEL', str(data))
        self.assertNotIn('OTHER_TEACHER_SENTINEL', str(data))
        with self.assertRaises(AccessError):
            self.env['edu.session'].with_user(self.public).search([])

    def test_default_uses_current_vietnam_week_without_writes(self):
        count = self.env['edu.week'].search_count([])
        with patch('odoo.fields.Date.context_today', return_value=date(2041, 1, 8)):
            data = self.page._get_values(' Public Zahra ')
        self.assertEqual(data['selected_week'], str(self.week.number))
        self.assertEqual(len(data['rows']), 1)
        self.assertEqual(self.env['edu.week'].search_count([]), count)

    def test_no_current_week_does_not_fall_back_to_old_lessons(self):
        with patch('odoo.fields.Date.context_today', return_value=date(2000, 1, 3)):
            data = self.page._get_values('public zahra')
        self.assertEqual(data['rows'], [])
        self.assertEqual(data['week_label'], 'Current week')

    def test_unknown_and_wildcard_names_do_not_list_teachers(self):
        for name in (None, '', '%', 'PUBLIC%', 'unknown', '\x00'):
            self.assertEqual(self.page._get_values(name)['status'], 404)
        self.teacher.active = False
        self.assertEqual(self.values()['status'], 404)

    def test_invalid_and_nonexistent_weeks(self):
        for number in ('abc', '-1', '0', '99875 OR 1=1', '2147483648'):
            self.assertEqual(self.page._get_values('public zahra', number)['status'], 400)
        self.assertEqual(self.page._get_values('public zahra', '2147483647')['status'], 404)

    def test_recording_is_drive_only_and_rejects_unsafe_links(self):
        for link in ('javascript:alert(1)', 'https://drive.google.com.evil.test/a',
                     'https://user:pass@drive.google.com/a', 'https://youtu.be/other'):
            self.session.google_drive_url = link
            self.assertFalse(self.values()['rows'][0]['recording'])
        self.session.google_drive_url = False
        self.assertFalse(self.values()['rows'][0]['recording'])

    def test_cancelled_absence_and_missing_hours_are_visible(self):
        self.session.write({'state': 'cancel', 'time_start': 0, 'time_end': 0})
        self.session.attendee_ids.present = False
        row = self.values()['rows'][0]
        self.assertTrue(row['cancelled'])
        self.assertTrue(row['students'][0]['absent'])
        self.assertEqual(row['time'], 'Time not set')

    def test_teacher_has_a_shareable_url(self):
        self.assertIn('/weekly-schedule?teacher=public+zahra', self.teacher.public_schedule_url)

    def test_private_links_are_unique_stable_and_scoped(self):
        token = self.teacher.schedule_edit_token
        self.assertEqual(len(token), 43)
        self.assertNotEqual(token, self.other.schedule_edit_token)
        self.env['edu.teacher']._ensure_schedule_edit_tokens()
        self.assertEqual(token, self.teacher.schedule_edit_token)
        self.assertNotIn(token, str(self.values()))
        self.assertFalse(self.page._editor('invalid'))
        data = self.page._get_values(self.teacher.name, str(self.week.number), editor=self.page._editor(token))
        self.assertTrue(data['edit_mode'])
        self.assertEqual([row['session_id'] for row in data['rows']], [self.session.id])
        self.teacher.active = False
        self.assertFalse(self.page._editor(token))

    def test_recording_updates_are_authorized_validated_and_detect_stale_edits(self):
        self.session.youtube_url = False
        original = self.session.google_drive_url
        link = 'https://drive.google.com/file/d/new_recording/view?usp=sharing'
        save = self.page._save_recording
        token = self.teacher.schedule_edit_token
        self.assertEqual(save('invalid', self.session.id, link, original)[0], 403)
        self.assertEqual(save(self.other.schedule_edit_token, self.session.id, link, original)[0], 404)
        for bad in ('javascript:alert(1)', 'https://drive.google.com.evil.test/a', 'https://youtu.be/test',
                    'https://user@drive.google.com/a', 'https://drive.google.com/' + 'a' * 2048):
            self.assertEqual(save(token, self.session.id, bad, original)[0], 400)
        self.assertEqual(self.session.google_drive_url, original)
        before = self.session.read(['teacher_id', 'date', 'teacher_rate', 'state', 'youtube_url'])[0]
        self.assertEqual(save(token, self.session.id, link, original), (200, ''))
        self.assertEqual(self.session.google_drive_url, link)
        self.assertEqual(save(token, self.session.id, original, original)[0], 409)
        self.assertEqual(self.session.read(list(before))[0], before)
        self.assertEqual(save(token, self.session.id, '', link), (200, ''))
        self.assertFalse(self.session.google_drive_url)

    def test_recording_can_be_added_after_payroll_closure(self):
        self.session.youtube_url = False
        self.session.with_context(edu_payroll_internal=True).write({'paid': True})
        status, error = self.page._save_recording(self.teacher.schedule_edit_token, self.session.id,
                                                'https://drive.google.com/file/d/paid_lesson/view',
                                                self.session.google_drive_url)
        self.assertEqual((status, error), (200, ''))
        self.assertTrue(self.session.paid)
        self.assertEqual(self.session.teacher_rate, 123456)

    def test_teacher_can_mark_absent_and_restore_present(self):
        attendee = self.session.attendee_ids
        self.session.write({'state': 'done', 'student_hours': 0.5, 'teacher_hours': 0.5})
        version = self.page._attendance_version(self.session)
        save = self.page._save_attendance
        token = self.teacher.schedule_edit_token
        self.assertGreater(attendee.charge_amount, 0)
        self.assertEqual(save(token, self.session.id, [str(attendee.id)], version), (200, ''))
        self.assertFalse(attendee.present)
        self.assertEqual(attendee.charge_amount, 0)
        self.assertEqual(self.session.paid_hours, 0)
        self.assertTrue(self.values()['rows'][0]['students'][0]['absent'])
        version = self.page._attendance_version(self.session)
        self.assertEqual(save(token, self.session.id, [], version), (200, ''))
        self.assertTrue(attendee.present)
        self.assertGreater(attendee.charge_amount, 0)
        self.assertEqual(self.session.paid_hours, 0.5)

    def test_attendance_rejects_other_teachers_and_unrelated_attendees(self):
        version = self.page._attendance_version(self.session)
        save = self.page._save_attendance
        self.assertEqual(save('invalid', self.session.id, [], version)[0], 403)
        self.assertEqual(save(self.other.schedule_edit_token, self.session.id, [], version)[0], 404)
        foreign_session = self.env['edu.session'].search([('teacher_id', '=', self.other.id)], limit=1)
        foreign = self.env['edu.session.attendee'].create({'session_id': foreign_session.id, 'student_id': self.student.id})
        for absent in ([str(foreign.id)], ['bad'], ['-1'], None):
            self.assertEqual(save(self.teacher.schedule_edit_token, self.session.id, absent, version)[0], 400)
        self.assertTrue(self.session.attendee_ids.present)
        self.assertTrue(foreign.present)

    def test_attendance_rejects_stale_roster_or_status(self):
        version = self.page._attendance_version(self.session)
        self.session.attendee_ids.present = False
        save = self.page._save_attendance
        self.assertEqual(save(self.teacher.schedule_edit_token, self.session.id, [], version)[0], 409)
        self.assertFalse(self.session.attendee_ids.present)
        version = self.page._attendance_version(self.session)
        student = self.env['edu.student'].create({'name_vi': 'New Roster Student'})
        self.env['edu.session.attendee'].create({'session_id': self.session.id, 'student_id': student.id})
        self.assertEqual(save(self.teacher.schedule_edit_token, self.session.id, [], version)[0], 409)

    def test_attendance_preserves_payroll_and_cancel_locks(self):
        save = self.page._save_attendance
        absent = [str(self.session.attendee_ids.id)]
        self.session.with_context(edu_payroll_internal=True).write({'paid': True})
        self.assertEqual(save(self.teacher.schedule_edit_token, self.session.id, absent,
                              self.page._attendance_version(self.session))[0], 409)
        self.session.with_context(edu_payroll_internal=True).write({'paid': False, 'state': 'cancel'})
        self.assertEqual(save(self.teacher.schedule_edit_token, self.session.id, absent,
                              self.page._attendance_version(self.session))[0], 409)
        self.assertTrue(self.session.attendee_ids.present)


@tagged('post_install', '-at_install')
class TestPublicScheduleHttp(HttpCase):
    def test_ajax_saves_return_json_and_refresh_concurrency_values(self):
        week = self.env['edu.week'].create({
            'number': 99879, 'date_from': '2046-12-31', 'date_to': '2047-01-06'})
        teacher = self.env['edu.teacher'].create({'name': 'Ajax Http Teacher'})
        student = self.env['edu.student'].create({'name_vi': 'Ajax Student'})
        session = self.env['edu.session'].create({'date': '2047-01-02', 'teacher_id': teacher.id,
            'attendee_ids': [(0, 0, {'student_id': student.id})]})
        self.authenticate(None, None)
        path = '/weekly-schedule/edit/' + teacher.schedule_edit_token
        response = self.url_open(path + '?week=' + str(week.number))
        tree = html.fromstring(response.content)
        headers = {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
        form = tree.xpath('//form[@class="attendance-form"]')[0]
        data = {el.get('name'): el.get('value', '') for el in form.xpath('.//input[@type="hidden"]')}
        data['absent'] = str(session.attendee_ids.id)
        response = self.url_open('/weekly-schedule/attendance', data=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertNotEqual(response.json()['original_attendance'], data['original_attendance'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(self.url_open('/weekly-schedule/attendance', data=data, headers=headers).status_code, 409)
        data['original_attendance'] = response.json()['original_attendance']
        data.pop('absent')
        self.assertTrue(self.url_open('/weekly-schedule/attendance', data=data, headers=headers).json()['success'])
        form = tree.xpath('//form[@class="recording-form"]')[0]
        data = {el.get('name'): el.get('value', '') for el in form.xpath('.//input')}
        data.pop('multipart', None)
        data['recording'] = 'https://drive.google.com/file/d/ajax_recording/view'
        response = self.url_open('/weekly-schedule/recording', data=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['recording'], data['recording'])
        self.assertEqual(self.url_open('/weekly-schedule/recording', data=data, headers=headers).status_code, 409)
        data['original_recording'] = response.json()['recording']
        data['recording'] = ''
        self.assertTrue(self.url_open('/weekly-schedule/recording', data=data, headers=headers).json()['success'])
        data['edit_token'] = 'invalid'
        response = self.url_open('/weekly-schedule/recording', data=data, headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()['success'])

    def test_anonymous_teacher_can_save_attendance(self):
        week = self.env['edu.week'].create({
            'number': 99878, 'date_from': '2046-01-01', 'date_to': '2046-01-07'})
        teacher = self.env['edu.teacher'].create({'name': 'Attendance Http Teacher'})
        students = self.env['edu.student'].create([{'name_vi': 'Attendance Alice'}, {'name_vi': 'Attendance Bob'}])
        session = self.env['edu.session'].create({'date': '2046-01-02', 'teacher_id': teacher.id,
            'attendee_ids': [(0, 0, {'student_id': student.id}) for student in students]})
        self.authenticate(None, None)
        path = '/weekly-schedule/edit/' + teacher.schedule_edit_token + '?week=' + str(week.number)
        response = self.url_open(path)
        form = html.fromstring(response.content).xpath('//form[@class="attendance-form"]')[0]
        payload = {el.get('name'): el.get('value', '') for el in form.xpath('.//input[@type="hidden"]')}
        payload['absent'] = [str(a.id) for a in session.attendee_ids]
        self.assertEqual(self.url_open('/weekly-schedule/attendance', data={
            k: v for k, v in payload.items() if k != 'csrf_token'}).status_code, 400)
        response = self.url_open('/weekly-schedule/attendance', data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Attendance saved successfully.', response.text)
        session.attendee_ids.invalidate_recordset()
        self.assertFalse(any(session.attendee_ids.mapped('present')))
        self.assertEqual(self.url_open('/weekly-schedule/attendance', data=payload).status_code, 409)
        response = self.url_open(path)
        form = html.fromstring(response.content).xpath('//form[@class="attendance-form"]')[0]
        payload = {el.get('name'): el.get('value', '') for el in form.xpath('.//input[@type="hidden"]')}
        response = self.url_open('/weekly-schedule/attendance', data=payload)
        self.assertEqual(response.status_code, 200)
        session.attendee_ids.invalidate_recordset()
        self.assertTrue(all(session.attendee_ids.mapped('present')))

    def test_anonymous_html_has_only_basic_schedule_data(self):
        week = self.env['edu.week'].create({
            'number': 99876, 'date_from': '2044-01-04', 'date_to': '2044-01-10'})
        teacher = self.env['edu.teacher'].create({'name': 'Public Http Teacher'})
        self.env['edu.session'].create({
            'date': '2044-01-10', 'teacher_id': teacher.id, 'time_start': 20, 'time_end': 20.5,
            'note': 'INTERNAL_HTTP_SENTINEL', 'google_drive_url': 'https://drive.google.com/file/d/test/view',
        })
        self.authenticate(None, None)
        response = self.url_open('/weekly-schedule?teacher=public+http+teacher&week=%s' % week.number)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.text.lstrip().startswith('<!DOCTYPE html>'))
        self.assertIn('PUBLIC HTTP TEACHER', response.text)
        self.assertIn('20:00', response.text)
        self.assertIn('https://drive.google.com/file/d/test/view', response.text)
        self.assertNotIn('INTERNAL_HTTP_SENTINEL', response.text)
        self.assertNotIn('web/login', response.text)
        self.assertIn('lang="en"', response.text)
        self.assertIn('Select week', response.text)
        self.assertNotIn('recording-form', response.text)
        self.assertNotIn(teacher.schedule_edit_token, response.text)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['X-Robots-Tag'], 'noindex, nofollow')
        self.assertEqual(self.url_open('/weekly-schedule?teacher=unknown').status_code, 404)
        self.assertEqual(self.url_open('/weekly-schedule?teacher=public+http+teacher&week=bad').status_code, 400)

    def test_teacher_can_save_recording_with_csrf_and_private_link(self):
        week = self.env['edu.week'].create({
            'number': 99877, 'date_from': '2045-01-02', 'date_to': '2045-01-08'})
        teacher = self.env['edu.teacher'].create({'name': 'Recording Http Teacher'})
        session = self.env['edu.session'].create({'date': '2045-01-02', 'teacher_id': teacher.id})
        self.authenticate(None, None)
        path = '/weekly-schedule/edit/' + teacher.schedule_edit_token
        response = self.url_open(path + '?week=' + str(week.number))
        self.assertEqual(response.status_code, 200)
        form = html.fromstring(response.content).xpath('//form[@class="recording-form"]')[0]
        payload = {el.get('name'): el.get('value', '') for el in form.xpath('.//input')}
        payload.pop('multipart', None)
        payload['recording'] = 'https://drive.google.com/file/d/http_recording/view'
        self.assertEqual(self.url_open('/weekly-schedule/recording', data={
            key: value for key, value in payload.items() if key != 'csrf_token'}).status_code, 400)
        response = self.url_open('/weekly-schedule/recording', data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Recording saved successfully.', response.text)
        session.invalidate_recordset()
        self.assertEqual(session.google_drive_url, payload['recording'])
        self.assertEqual(self.url_open('/weekly-schedule/recording', data=payload).status_code, 409)
        payload['edit_token'] = 'invalid'
        self.assertEqual(self.url_open('/weekly-schedule/recording', data=payload).status_code, 403)
        self.assertEqual(self.url_open('/weekly-schedule/edit/invalid').status_code, 403)
