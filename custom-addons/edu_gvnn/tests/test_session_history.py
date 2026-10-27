from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSessionHistory(TransactionCase):
    def setUp(self):
        super().setUp()
        self.teacher = self.env['edu.teacher'].create({'name': 'History Teacher'})
        self.student = self.env['edu.student'].create({'name_vi': 'History Student <script>'})
        self.session = self.env['edu.session'].create({
            'date': '2048-01-02', 'teacher_id': self.teacher.id,
            'time_start': 17, 'time_end': 17.5,
            'google_drive_url': 'https://drive.google.com/file/d/history_part1/view',
        })
        self.env.cr.precommit.run()

    def flush_tracking(self):
        self.env.flush_all()
        self.env.cr.precommit.run()

    def test_session_fields_record_old_new_author_and_time(self):
        before = self.session.message_ids
        self.session.write({'state': 'cancel', 'youtube_url': 'https://youtu.be/historytest'})
        self.flush_tracking()
        messages = self.session.message_ids - before
        tracked = messages.tracking_value_ids
        state = tracked.filtered(lambda value: value.field_id.name == 'state')
        video = tracked.filtered(lambda value: value.field_id.name == 'youtube_url')
        self.assertEqual((state.old_value_char, state.new_value_char), ('Đã dạy', 'Nghỉ buổi học'))
        self.assertEqual(video.new_value_char, 'https://youtu.be/historytest')
        self.assertEqual(state.mail_message_id.author_id, self.env.user.partner_id)
        self.assertTrue(state.mail_message_id.date)

    def test_attendee_create_update_unlink_and_html_escaping(self):
        before = self.session.message_ids
        attendee = self.env['edu.session.attendee'].create({
            'session_id': self.session.id, 'student_id': self.student.id})
        message = self.session.message_ids - before
        self.assertEqual(len(message), 1)
        self.assertIn('Thêm học viên', message.body)
        self.assertIn('&lt;script&gt;', message.body.lower())
        self.assertNotIn('<script>', message.body.lower())
        attendee.write({'present': False})
        message = self.session.message_ids[:1]
        self.assertIn('Có mặt → Nghỉ', message.body)
        self.assertEqual(message.author_id, self.env.user.partner_id)
        count = len(self.session.message_ids)
        attendee.write({'present': False})
        self.assertEqual(len(self.session.message_ids), count)
        attendee.unlink()
        self.assertIn('Xóa học viên', self.session.message_ids[:1].body)

    def test_parts_create_update_unlink_and_noop(self):
        part = self.env['edu.session.recording.part'].create({
            'session_id': self.session.id, 'number': 2,
            'google_drive_url': 'https://drive.google.com/file/d/history_part2/view'})
        self.assertIn('Thêm phần video', self.session.message_ids[:1].body)
        part.youtube_url = 'https://youtu.be/part2history'
        self.assertIn('https://youtu.be/part2history', self.session.message_ids[:1].body)
        count = len(self.session.message_ids)
        part.youtube_url = 'https://youtu.be/part2history'
        self.assertEqual(len(self.session.message_ids), count)
        part.youtube_url = False
        part.unlink()
        self.assertIn('Xóa phần video', self.session.message_ids[:1].body)

    def test_inline_relational_commands_and_classes_are_logged(self):
        classroom = self.env['edu.class'].create({'name': 'History Class'})
        self.session.write({
            'class_ids': [fields.Command.link(classroom.id)],
            'attendee_ids': [fields.Command.create({'student_id': self.student.id})],
        })
        self.flush_tracking()
        self.assertTrue(self.session.message_ids.tracking_value_ids.filtered(
            lambda value: value.field_id.name == 'class_ids' and classroom.display_name in value.new_value_char))
        self.assertTrue(self.session.message_ids.filtered(lambda message: 'Thêm học viên' in message.body))

    def test_disabled_tracking_and_failed_write_do_not_log(self):
        before = self.session.message_ids
        attendee = self.env['edu.session.attendee'].with_context(tracking_disable=True).create({
            'session_id': self.session.id, 'student_id': self.student.id})
        attendee.present = False
        self.assertEqual(self.session.message_ids, before)
        self.session.paid = True
        self.flush_tracking()
        before = self.session.message_ids
        with self.assertRaises(UserError), self.env.cr.savepoint():
            attendee.with_context(tracking_disable=False).present = True
        self.assertEqual(self.session.message_ids, before)

    def test_rolled_back_change_does_not_leave_history(self):
        before = self.session.message_ids
        with self.assertRaises(ValueError), self.env.cr.savepoint():
            self.env['edu.session.attendee'].create({
                'session_id': self.session.id, 'student_id': self.student.id})
            raise ValueError('Simulate rollback')
        self.assertEqual(self.session.message_ids, before)

    def test_staff_changes_are_attributed_to_actual_user(self):
        staff = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'History Staff', 'login': 'history-staff',
            'groups_id': [fields.Command.set([self.env.ref('edu_gvnn.group_edu_staff').id])],
        })
        before = self.session.message_ids
        session = self.session.with_user(staff)
        session.write({'youtube_url': 'https://youtu.be/staffchange'})
        attendee = self.env['edu.session.attendee'].with_user(staff).create({
            'session_id': session.id, 'student_id': self.student.id})
        attendee.present = False
        self.flush_tracking()
        messages = self.session.message_ids - before
        self.assertTrue(messages)
        self.assertEqual(messages.mapped('author_id'), staff.partner_id)
