from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from .test_transfer import response


@tagged('post_install', '-at_install')
class TestVideoTitles(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env.ref('edu_video.config_default').sudo().auto_upload = False
        self.Job = self.env['edu.video.job']
        self.week = self.env['edu.week'].create({
            'number': 99891, 'date_from': '2049-02-01', 'date_to': '2049-02-07'})
        self.teacher = self.env['edu.teacher'].create({'name': 'Title Test Hope', 'teaching_title': 'ms'})
        self.students = self.env['edu.student'].create([
            {'name_vi': 'Title Test Kelly', 'name_en': 'KELLY'},
            {'name_vi': 'Title Test Lily', 'name_en': 'LILY'}])
        self.session = self.env['edu.session'].create({
            'date': '2049-02-01', 'teacher_id': self.teacher.id,
            'google_drive_url': 'https://drive.google.com/file/d/title_first_12345/view',
            'attendee_ids': [(0, 0, {'student_id': student.id}) for student in self.students]})

    def test_exact_user_example(self):
        example = SimpleNamespace(
            teacher_id=SimpleNamespace(name='HOPE', teaching_title='ms'),
            attendee_ids=[SimpleNamespace(student_id=SimpleNamespace(name_en=name, name_vi=''))
                          for name in ['KELLY', 'LILY']], extra_participants='',
            week_id=SimpleNamespace(number=102),
            _recording_parts=lambda: [{'drive': 'video', 'youtube': ''}])
        self.assertEqual(self.Job._youtube_title(example, strict=True),
                         'KIMENGLISH - MS HOPE - Kelly & Lily (WEEK 102)')

    def test_mr_single_student_and_vietnamese_fallback(self):
        self.teacher.teaching_title = 'mr'
        self.session.attendee_ids[1:].unlink()
        self.assertEqual(self.Job._youtube_title(self.session, strict=True),
                         'KIMENGLISH - MR TITLE TEST HOPE - Kelly (WEEK 99891)')
        self.students[0].name_en = False
        self.assertIn(' - Title Test Kelly (WEEK 99891)', self.Job._youtube_title(self.session, strict=True))

    def test_both_parts_are_numbered_and_names_are_not_filtered_by_attendance(self):
        self.session.attendee_ids[1].present = False
        part = self.env['edu.session.recording.part'].create({'session_id': self.session.id,
            'number': 2, 'google_drive_url': 'https://drive.google.com/file/d/title_second_12345/view'})
        jobs = self.session._enqueue_video()
        self.assertEqual(jobs.filtered(lambda j: not j.recording_part_id).title,
                         'KIMENGLISH - MS TITLE TEST HOPE - Kelly & Lily (WEEK 99891) (1)')
        self.assertEqual(jobs.filtered('recording_part_id').title,
                         'KIMENGLISH - MS TITLE TEST HOPE - Kelly & Lily (WEEK 99891) (2)')
        self.assertEqual(jobs.filtered('recording_part_id').recording_part_id, part)

    def test_queued_title_refreshes_before_upload_and_resume_keeps_it(self):
        job = self.session._enqueue_video()
        self.session.write({'time_start': 17.5, 'time_end': 18.0})
        self.env['edu.session.recording.part'].create({'session_id': self.session.id,
            'number': 2, 'google_drive_url': 'https://drive.google.com/file/d/title_second_12345/view'})
        with patch.object(type(self.Job), '_request', side_effect=[
                response(body={'items': [{'id': 'title-channel'}]}),
                response(headers={'Location': 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=fake'})
                ]) as request, patch.object(type(self.Job), '_checkpoint'):
            job._start_upload(SimpleNamespace(channel_id='title-channel', privacy='public',
                                             metadata_language='vi', audio_language='en'))
        expected = 'KIMENGLISH - MS TITLE TEST HOPE - Kelly & Lily (WEEK 99891) (1)'
        self.assertEqual(request.call_args_list[1].kwargs['json']['snippet']['title'], expected)
        self.assertEqual(job.title, expected)
        sent_description = request.call_args_list[1].kwargs['json']['snippet']['description']
        self.assertIn('17:30–18:00', sent_description)
        self.assertEqual(job.description, sent_description)
        self.teacher.name = 'Renamed Title Teacher'
        self.session.time_start = 16.0
        job._refresh_upload_title()
        self.assertEqual(job.title, expected)
        self.assertEqual(job.description, sent_description)

    def test_description_uses_vietnamese_schedule_and_handles_midnight(self):
        lesson = SimpleNamespace(date=date(2026, 10, 27), time_start=23.5, time_end=0.0,
                                 teacher_id=SimpleNamespace(name='Hope', teaching_title='ms'),
                                 week_id=SimpleNamespace(number=103))
        self.assertEqual(self.Job._youtube_description(lesson).splitlines()[0],
                         '23:30–00:00 Thứ Ba 27/10/2026')
        lesson.date = date(2026, 10, 26)
        lesson.time_start, lesson.time_end = 20.5, 21.0
        description = self.Job._youtube_description(lesson)
        self.assertEqual(description.splitlines()[0],
                         '20:30–21:00 Thứ Hai 26/10/2026')
        self.assertIn('Buổi học tiếng Anh trực tuyến cùng MS HOPE tại Kim Academy — tuần 103.', description)
        self.assertIn('• Giáo viên: MS HOPE\n• Tuần học: 103', description)
        self.assertIn('• Ngày học: Thứ Hai, 26/10/2026\n• Giờ học: 20:30–21:00 (giờ Việt Nam)', description)
        self.assertIn('Thông tin chương trình học: https://kimacademy.uk/', description)
        self.assertIn('#KimAcademy #HocTiengAnh #TiengAnhOnline', description)
        self.assertTrue(description.endswith(
            '--------------------------------------\n'
            '► FOLLOW KIM ACADEMY OFFICIAL:\n'
            'YouTube: https://www.youtube.com/@YURYONG90\n'
            'Facebook: https://www.facebook.com/mskim.kimacademy\n'
            'Email: kimacademy.edu@gmail.com\n\n'
            '© Bản quyền thuộc về Kim Academy Official ☞ Do not Reup\n'
            '© Copyright by Kim Academy Official ☞ Do not Reup'))
        lesson.date = date(2026, 11, 1)
        lesson.time_start = lesson.time_end = 0.0
        description = self.Job._youtube_description(lesson)
        self.assertEqual(description.splitlines()[0], 'Chưa cập nhật Chủ Nhật 01/11/2026')

    def test_description_uses_actual_teacher_and_handles_missing_week(self):
        lesson = SimpleNamespace(date=date(2026, 10, 28), time_start=17.5, time_end=18.0,
                                 teacher_id=SimpleNamespace(name='  Moshood  ', teaching_title='mr'),
                                 week_id=False)
        description = self.Job._youtube_description(lesson)
        self.assertIn('cùng MR MOSHOOD tại Kim Academy', description)
        self.assertIn('• Tuần học: Chưa cập nhật', description)
        self.assertNotIn('HOPE', description)

    def test_missing_fields_stop_before_google_request(self):
        job = self.session._enqueue_video()
        with patch.object(type(self.Job), '_request') as request:
            self.teacher.teaching_title = False
            with self.assertRaises(UserError):
                job._start_upload(SimpleNamespace())
            self.teacher.teaching_title = 'ms'
            self.session.week_id = False
            with self.assertRaises(UserError):
                job._start_upload(SimpleNamespace())
            self.session.week_id = self.week
            self.session.attendee_ids.unlink()
            with self.assertRaises(UserError):
                job._start_upload(SimpleNamespace())
            request.assert_not_called()

    def test_youtube_title_limit_and_invalid_characters_are_validated(self):
        self.teacher.name = 'X' * 100
        with self.assertRaises(UserError):
            self.Job._youtube_title(self.session, strict=True)
        self.teacher.name = 'Title <Teacher>'
        with self.assertRaises(UserError):
            self.Job._youtube_title(self.session, strict=True)
