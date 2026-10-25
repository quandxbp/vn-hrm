from odoo.tests import TransactionCase, HttpCase, tagged
from odoo.exceptions import AccessError
from lxml import html


@tagged('post_install', '-at_install')
class TestRecordingParts(TransactionCase):
    def setUp(self):
        super().setUp()
        self.teacher = self.env['edu.teacher'].create({'name': 'Multipart Teacher'})
        self.session = self.env['edu.session'].create({'date': '2048-01-02', 'teacher_id': self.teacher.id,
            'google_drive_url': 'https://drive.google.com/file/d/part_one_123456/view'})
        self.page = self.env['edu.public.schedule'].with_user(self.env.ref('base.public_user'))
        self.url2 = 'https://drive.google.com/file/d/part_two_123456/view'
        self.url3 = 'https://drive.google.com/file/d/part_three_123456/view'

    def save(self, ids, urls, first=None, version=None):
        return self.page._save_recordings(self.teacher.schedule_edit_token, self.session.id,
            self.session.google_drive_url if first is None else first, ids, urls,
            version or self.page._recording_version(self.session))

    def test_save_multiple_parts_and_keep_legacy_first_link(self):
        first = self.session.google_drive_url
        self.assertEqual(self.save(['', ''], [self.url2, self.url3]), (200, ''))
        self.assertEqual(self.session.google_drive_url, first)
        parts = self.session.recording_part_ids
        self.assertEqual(parts.mapped('number'), [2, 3])
        self.assertEqual(parts.mapped('google_drive_url'), [self.url2, self.url3])
        self.assertEqual(self.save([str(p.id) for p in parts], parts.mapped('google_drive_url')), (200, ''))
        self.assertEqual(len(self.session.recording_part_ids), 2)
        self.assertFalse(self.session.copy().recording_part_ids)
        with self.assertRaises(AccessError):
            self.env['edu.session.recording.part'].with_user(self.env.ref('base.public_user')).search([])

    def test_validation_and_stale_updates_are_atomic(self):
        first = self.session.google_drive_url
        version = self.page._recording_version(self.session)
        self.assertEqual(self.page._save_recordings('invalid', self.session.id, first, [], [], version)[0], 403)
        other_teacher = self.env['edu.teacher'].create({'name': 'Multipart Other Teacher'})
        self.assertEqual(self.page._save_recordings(other_teacher.schedule_edit_token, self.session.id,
                         first, [], [], version)[0], 404)
        for ids, urls in [([''], ['javascript:alert(1)']), ([''], [first + '?usp=sharing']), ([''], ['']),
                          ([''], [self.url2, self.url3]), ([''] * 10, [self.url2] * 10)]:
            self.assertEqual(self.save(ids, urls)[0], 400)
            self.assertFalse(self.session.recording_part_ids)
            self.assertEqual(self.session.google_drive_url, first)
        self.assertEqual(self.save([''], [self.url2]), (200, ''))
        self.assertEqual(self.save([], [], version=version)[0], 409)
        other = self.env['edu.session'].create({'date': '2048-01-03', 'teacher_id': self.teacher.id,
            'google_drive_url': first})
        foreign = self.env['edu.session.recording.part'].create({'session_id': other.id, 'google_drive_url': self.url3})
        self.assertEqual(self.save([str(foreign.id)], [self.url3])[0], 404)

    def test_removing_part_preserves_remaining_numbers_and_youtube_mapping(self):
        self.save(['', ''], [self.url2, self.url3])
        second, third = self.session.recording_part_ids
        self.assertEqual(self.save([str(third.id)], [self.url3]), (200, ''))
        self.assertFalse(second.exists())
        self.assertEqual(third.number, 3)
        third.youtube_url = 'https://youtu.be/thirdvideo1'
        first = self.session.google_drive_url
        self.assertEqual(self.save([str(third.id)], [self.url2], first=self.url2)[0], 400)
        self.assertEqual(self.save([str(third.id)], [self.url2], first=self.url3)[0], 409)
        self.assertEqual(self.session.google_drive_url, first)
        self.assertEqual(third.google_drive_url, self.url3)
        self.assertEqual(self.save([], [])[0], 409)

    def test_export_contains_all_links_and_only_marks_fully_uploaded(self):
        self.save([''], [self.url2])
        self.session.youtube_url = 'https://youtu.be/firstvideo1'
        export = self.env['edu.export.week.wizard']
        links, posted = export._weekly_video_values(self.session)
        self.assertIn(self.url2, links[1])
        self.assertFalse(posted)
        self.session.recording_part_ids.youtube_url = 'https://youtu.be/secondvideo'
        links, posted = export._weekly_video_values(self.session)
        self.assertIn('https://youtu.be/secondvideo', links[0])
        self.assertEqual(posted, 1)


@tagged('post_install', '-at_install')
class TestRecordingPartsHttp(HttpCase):
    def test_teacher_saves_two_links_in_one_request(self):
        week = self.env['edu.week'].create({'number': 99880, 'date_from': '2049-01-04', 'date_to': '2049-01-10'})
        teacher = self.env['edu.teacher'].create({'name': 'Multipart Http Teacher'})
        session = self.env['edu.session'].create({'date': '2049-01-04', 'teacher_id': teacher.id})
        self.authenticate(None, None)
        path = '/weekly-schedule/edit/' + teacher.schedule_edit_token + '?week=' + str(week.number)
        response = self.url_open(path)
        form = html.fromstring(response.content).xpath('//form[@class="recording-form"]')[0]
        data = {el.get('name'): el.get('value', '') for el in form.xpath('.//input')}
        data.update(recording='https://drive.google.com/file/d/http_part_one_123/view', part_id='',
                    part_url='https://drive.google.com/file/d/http_part_two_123/view')
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        self.assertEqual(self.url_open('/weekly-schedule/recording', data={
            k: v for k, v in data.items() if k != 'csrf_token'}, headers=headers).status_code, 400)
        response = self.url_open('/weekly-schedule/recording', data=data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result['recording_parts']), 2)
        self.assertEqual(result['recording_parts'][1]['url'], data['part_url'])
        self.assertGreater(result['recording_parts'][1]['id'], 0)
        session.invalidate_recordset()
        self.assertEqual(len(session.recording_part_ids), 1)
        public = self.url_open('/weekly-schedule?teacher=Multipart+Http+Teacher&week=' + str(week.number))
        self.assertIn(data['recording'], public.text)
        self.assertIn(data['part_url'], public.text)
        self.assertNotIn(teacher.schedule_edit_token, public.text)
        self.assertEqual(self.url_open('/weekly-schedule/recording', data=data, headers=headers).status_code, 409)
