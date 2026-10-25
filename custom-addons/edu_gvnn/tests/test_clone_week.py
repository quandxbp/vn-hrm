from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCloneWeek(TransactionCase):
    def setUp(self):
        super().setUp()
        self.source = self.env['edu.week'].create({'number': 99901,
            'date_from': '2035-01-01', 'date_to': '2035-01-07'})
        self.target = self.env['edu.week'].create({'number': 99902,
            'date_from': '2035-03-05', 'date_to': '2035-03-11'})
        self.teacher = self.env['edu.teacher'].create({'name': 'Clone Week Test Teacher'})
        self.env['edu.teacher.rate'].create({'teacher_id': self.teacher.id,
            'date_from': '2035-01-01', 'rate': 100000})
        self.env['edu.teacher.rate'].create({'teacher_id': self.teacher.id,
            'date_from': '2035-03-01', 'rate': 200000})
        self.student = self.env['edu.student'].create({'name_vi': 'Clone Week Test Student'})
        self.session = self.env['edu.session'].create({'date': '2035-01-02',
            'teacher_id': self.teacher.id, 'time_start': 17.5, 'time_end': 18,
            'note': 'Old private note', 'completion_note': 'Old result',
            'recording_url': 'https://example.com/old', 'video_posted': True,
            'google_drive_url': 'https://drive.google.com/file/d/clone_source_12345/view',
            'youtube_url': 'https://youtu.be/existing123',
            'import_key': 'clone-test-old',
            'attendee_ids': [fields.Command.create({'student_id': self.student.id,
                'present': False, 'score': 8, 'block_price': 777})]})
        self.session.write({'paid': True})

    def wizard(self, **values):
        return self.env['edu.clone.week.wizard'].create({
            'source_week_id': self.source.id, **values})

    def test_create_week_and_lessons_together(self):
        wizard = self.wizard()
        self.assertEqual(wizard.new_week_number, 99903)
        self.assertEqual(wizard.new_date_from, self.target.date_to + timedelta(days=1))
        wizard.action_clone()
        self.assertEqual(wizard.target_week_id.number, 99903)
        self.assertEqual(wizard.target_week_id.date_to - wizard.target_week_id.date_from, timedelta(days=6))
        self.assertEqual(len(wizard.created_ids), 1)
        self.assertEqual(wizard.created_ids.week_id, wizard.target_week_id)
        wizard.action_clone()
        self.assertEqual(self.env['edu.week'].search_count([('number', '=', 99903)]), 1)

    def test_duplicate_new_week_number_rejected(self):
        wizard = self.wizard(new_week_number=self.target.number)
        with self.assertRaises(UserError):
            wizard.action_clone()
        self.assertFalse(wizard.completed)

    def test_new_week_rolled_back_if_payroll_locked(self):
        period = self.env['edu.payroll.period'].create({'date_from': '2035-03-01'})
        period.action_lock()
        wizard = self.wizard()
        with self.assertRaises(UserError):
            wizard.action_clone()
        self.assertFalse(self.env['edu.week'].search([('number', '=', 99903)]))

    def test_new_week_overlapping_dates_rejected(self):
        wizard = self.wizard(new_date_from=self.target.date_from)
        with self.assertRaises(UserError):
            wizard.action_clone()

    def test_clone_arbitrary_old_week_resets_results_and_prices(self):
        wizard = self.wizard()
        wizard.action_clone()
        new = wizard.created_ids
        self.assertEqual(len(new), 1)
        self.assertEqual(new.date, date(2035, 3, 13))
        self.assertEqual(new.date.weekday(), self.session.date.weekday())
        self.assertEqual(new.week_id, wizard.target_week_id)
        self.assertEqual(new.teacher_id, self.teacher)
        self.assertEqual(new.time_start, 17.5)
        self.assertEqual(new.attendee_ids.student_id, self.student)
        self.assertTrue(new.attendee_ids.present)
        self.assertEqual(new.attendee_ids.score, 0)
        self.assertNotEqual(new.attendee_ids.block_price, 777)
        self.assertEqual(new.teacher_rate, 200000)
        for field in ('paid', 'import_key', 'note', 'completion_note', 'recording_url',
                      'video_posted', 'google_drive_url', 'youtube_url'):
            self.assertFalse(new[field], field)
        self.assertTrue(self.session.paid)
        self.assertEqual(self.session.teacher_rate, 100000)
        self.assertFalse(self.session.attendee_ids.present)
        self.assertEqual(self.session.attendee_ids.score, 8)

    def test_repeat_and_duplicate_new_week_do_not_duplicate(self):
        first = self.wizard()
        number, start = first.new_week_number, first.new_date_from
        first.action_clone()
        first.action_clone()
        second = self.wizard(new_week_number=number, new_date_from=start)
        with self.assertRaises(UserError):
            second.action_clone()
        self.assertEqual(self.env['edu.session'].search_count([('week_id', '=', first.target_week_id.id)]), 1)

    def test_cancelled_source_is_optional_and_new_lesson_is_done(self):
        self.session.with_context(edu_payroll_internal=True).write({'state': 'cancel'})
        with self.assertRaises(UserError):
            self.wizard(include_cancelled=False).action_clone()
        wizard = self.wizard()
        self.assertTrue(wizard.include_cancelled)
        wizard.action_clone()
        self.assertEqual(wizard.created_ids.state, 'done')

    def test_same_or_older_target_is_rejected(self):
        with self.assertRaises(UserError):
            self.wizard(new_date_from=self.source.date_from).action_clone()
        with self.assertRaises(UserError):
            self.wizard(new_date_from='2034-01-01').action_clone()

    def test_target_payroll_locked_is_rejected_without_creating(self):
        period = self.env['edu.payroll.period'].create({'date_from': '2035-03-01'})
        period.action_lock()
        with self.assertRaises(UserError):
            self.wizard().action_clone()
        self.assertFalse(self.env['edu.week'].search([('number', '=', 99903)]))

    def test_source_longer_than_week_rejected(self):
        self.source.date_to = self.source.date_from + timedelta(days=7)
        with self.assertRaises(UserError):
            self.wizard().action_clone()

    def test_nonstaff_cannot_clone(self):
        wizard = self.wizard()
        with self.assertRaises(UserError):
            wizard.with_user(self.env.ref('base.public_user')).action_clone()

    def test_preserves_weekday_with_different_week_start(self):
        wizard = self.wizard(new_date_from='2035-03-13')
        wizard.action_clone()
        self.assertEqual(wizard.created_ids.date, date(2035, 3, 13))
        self.assertEqual(wizard.created_ids.date.weekday(), self.session.date.weekday())

    def test_partial_historical_source_week_is_supported(self):
        self.source.date_to = '2035-01-04'
        wizard = self.wizard()
        wizard.action_clone()
        self.assertEqual(len(wizard.created_ids), 1)

    def test_testing_lesson_keeps_classes_without_attendees(self):
        classroom = self.env['edu.class'].create({'name': 'Clone Testing Class'})
        self.env['edu.session'].create({'date': '2035-01-03', 'teacher_id': self.teacher.id,
            'session_type': 'testing', 'time_start': 19, 'time_end': 19.5,
            'class_ids': [fields.Command.set(classroom.ids)]})
        wizard = self.wizard()
        wizard.action_clone()
        testing = wizard.created_ids.filtered(lambda s: s.session_type == 'testing')
        self.assertEqual(len(testing), 1)
        self.assertEqual(testing.class_ids, classroom)
        self.assertFalse(testing.attendee_ids)
