import copy
import json

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .test_review import report_v2
from ..models.report import validate_report, generation_schema


def observation(key='student_1'):
    return {'student_key': key, 'attendance': 'present', 'comment': 'Có thông báo vào phòng và giáo viên chào học sinh.',
        'first_observed_part': 1, 'first_observed_at': '00:50', 'join_confirmed': True,
        'already_present_at_start': False, 'evidence': [{'part': 1, 'start': '00:49', 'end': '00:55'}],
        'attention_events': [{'comment': 'Không đáp lại ba lượt gọi trực tiếp khi đường truyền vẫn hoạt động.',
            'evidence': [{'part': 1, 'start': '01:10', 'end': '01:20'}]}]}


@tagged('post_install', '-at_install')
class TestStudentReview(TransactionCase):
    def setUp(self):
        super().setUp()
        self.roster = [{'key': 'student_1', 'label': 'Alex', 'aliases': ['Alex']}]

    def validate(self, item, durations=None, data=None):
        data = data or report_v2()
        data['student_observations'] = [item]
        return validate_report(data, durations or {1: 120}, require_v2=True, require_students=True,
                               roster=self.roster, planned_minutes=30)

    def test_late_delay_is_locally_calculated_with_different_denominators(self):
        values = self.validate(observation())
        self.assertEqual(values['student_alert_count'], 1)
        for text in ('Alex', '00:40', '30 phút theo lịch', 'dạy thực tế 01:20', 'tổng video 02:00', 'Phần 1 · 00:50'):
            self.assertIn(text, values['student_report'])
        self.assertIn('Không đáp lại ba lượt gọi', values['student_report'])

    def test_first_speaking_time_is_not_assumed_to_be_join_time(self):
        item = observation()
        item.update(join_confirmed=False, attention_events=[])
        values = self.validate(item)
        self.assertIn('Độ trễ: chưa xác định', values['student_report'])
        self.assertEqual(values['student_alert_count'], 0)

    def test_not_observed_is_provisional_and_requires_all_parts(self):
        item = observation()
        item.update(attendance='not_observed', first_observed_part=None, first_observed_at=None,
                    join_confirmed=False, attention_events=[])
        self.assertIn('cần xác nhận vắng', self.validate(item)['student_report'])
        data = report_v2()
        data['parts'].append({'part': 2, 'teaching_segments': []})
        values = self.validate(item, {1: 120, 2: 60}, data)
        self.assertIn('chưa thể kết luận học sinh vắng', values['student_report'])
        self.assertNotIn('CẢNH BÁO: Chưa thấy', values['student_report'])

    def test_cannot_invent_late_duration_between_discontinuous_clips(self):
        item = observation()
        item.update(first_observed_part=2, first_observed_at='00:10', attention_events=[],
                    evidence=[{'part': 2, 'start': '00:09', 'end': '00:12'}])
        data = report_v2()
        data['parts'].append({'part': 2, 'teaching_segments': []})
        self.assertIn('Độ trễ: chưa xác định', self.validate(item, {1: 120, 2: 60}, data)['student_report'])

    def test_unknown_identity_can_remain_uncertain_without_fake_evidence(self):
        item = observation()
        item.update(attendance='uncertain', first_observed_part=None, first_observed_at=None,
                    join_confirmed=False, attention_events=[], evidence=[])
        values = self.validate(item)
        self.assertIn('Chưa xác định được tình trạng', values['student_report'])
        self.assertEqual(values['student_alert_count'], 0)

    def test_rejects_wrong_identity_times_and_unsupported_claims(self):
        for change in (
            {'student_key': 'invented'}, {'first_observed_at': '03:00'}, {'first_observed_part': True},
            {'first_observed_at': None}, {'evidence': []}, {'join_confirmed': 'true'},
            {'attendance': 'uncertain'},
            {'attention_events': [{'comment': 'No evidence', 'evidence': []}]},
        ):
            with self.subTest(change=change), self.assertRaises(UserError):
                item = observation()
                item.update(change)
                self.validate(item)

    def test_unsupported_absence_and_inconsistent_start_do_not_discard_valid_teacher_report(self):
        item = observation()
        item.update(attendance='not_observed', first_observed_part=None, first_observed_at=None,
                    join_confirmed=False, attention_events=[], evidence=[])
        values = self.validate(item)
        self.assertEqual(values['score_total'], 7.5)
        self.assertIn('Chưa xác định được tình trạng', values['student_report'])
        self.assertIn('chưa thể kết luận học sinh vắng', values['student_report'])
        self.assertEqual(values['student_alert_count'], 1)
        item = observation()
        item.update(join_confirmed=False, already_present_at_start=True, attention_events=[])
        values = self.validate(item)
        self.assertIn('chưa đủ căn cứ xác nhận đã tham gia từ 00:00', values['student_report'])
        self.assertIn('Độ trễ: chưa xác định', values['student_report'])
        self.assertNotIn('Đã tham gia từ đầu bản ghi', values['student_report'])

    def test_missing_or_duplicate_students_and_old_reports(self):
        data = report_v2()
        data.pop('student_observations')
        self.assertIn('score_total', validate_report(data, {1: 120}, require_v2=True))
        with self.assertRaises(UserError):
            validate_report(data, {1: 120}, require_students=True, roster=self.roster)
        data['student_observations'] = [observation(), copy.deepcopy(observation())]
        roster = self.roster + [{'key': 'student_2', 'label': 'Lily'}]
        with self.assertRaises(UserError):
            validate_report(data, {1: 120}, require_students=True, roster=roster)
        self.assertNotIn('student_observations', generation_schema(include_students=False)['properties'])

    def test_conflicting_join_flags_keep_teacher_report_without_claiming_lateness(self):
        item = observation()
        item['already_present_at_start'] = True
        original = copy.deepcopy(item)
        values = self.validate(item)
        self.assertEqual(values['score_total'], 7.5)
        self.assertIn('cờ vào lớp mâu thuẫn', values['student_report'])
        self.assertIn('Độ trễ: chưa xác định', values['student_report'])
        self.assertNotIn('CẢNH BÁO: Vào trễ', values['student_report'])
        self.assertNotIn('Đã tham gia từ đầu bản ghi', values['student_report'])
        self.assertEqual(item, original)

    def test_roster_is_snapshotted_and_prompt_uses_only_this_roster(self):
        config = self.env.ref('edu_video.config_default').sudo()
        config.write({'review_enabled': True, 'review_auto': False, 'review_api_key': 'fake',
                      'drive_state': 'connected', 'refresh_token': 'fake'})
        teacher = self.env['edu.teacher'].create({'name': 'Student Review Test Teacher'})
        student = self.env['edu.student'].create({'name_vi': 'Học sinh kiểm thử', 'name_en': 'Alex'})
        session = self.env['edu.session'].create({'teacher_id': teacher.id, 'date': '2051-03-01',
            'time_start': 18, 'time_end': 18.5, 'google_drive_url': 'https://drive.google.com/file/d/student_review_test/view',
            'attendee_ids': [(0, 0, {'student_id': student.id})]})
        review = session._queue_ai_review()
        self.assertEqual(review.planned_minutes, 30)
        self.assertTrue(review.source_current)
        payload = json.dumps(review._analysis_payload(), ensure_ascii=False)
        self.assertIn(student.name_en, payload)
        self.assertIn('student_observations', payload)
        student.name_en = 'Changed name'
        self.assertIn('ALEX', review.roster_snapshot[0]['label'])
        self.assertFalse(review.source_current)
