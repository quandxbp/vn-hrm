from datetime import date, datetime
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.addons.edu_zalo.models.zalo import split_message, TZ


@tagged('post_install', '-at_install')
class TestZaloSchedule(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env['edu.zalo.group'].create({'name': 'Zalo test only', 'zalo_id': 'TEST-NOT-A-REAL-GROUP'})
        cls.config = cls.env['edu.zalo.config'].create({'group_id': cls.group.id,
            'confirmed_group_id': cls.group.id, 'preview_date': '2026-10-23'})
        cls.day = date(2026, 10, 23)
        cls.teacher = cls.env['edu.teacher'].create({'name': 'ZALO TEST TEACHER'})
        cls.student = cls.env['edu.student'].create({'name_vi': 'ZALO TEST', 'name_en': 'STUDENT'})
        cls.session = cls.env['edu.session'].create({'date': cls.day, 'teacher_id': cls.teacher.id,
            'time_start': 17.5, 'time_end': 18, 'attendee_ids': [(0, 0, {'student_id': cls.student.id})]})

    def test_preview_and_no_sessions(self):
        text = self.config._schedule_text(self.day)
        self.assertIn('GV ZALO TEST TEACHER\n17:30–18:00', text)
        self.assertIn('17:30–18:00: ZALO TEST - STUDENT', text)
        self.session.action_cancel()
        self.assertNotIn('ZALO TEST TEACHER', self.config._schedule_text(self.day))
        with self.assertRaises(UserError):
            self.config._queue(date(2040, 1, 1))

    def test_queue_requires_confirmation_and_deduplicates(self):
        self.config.confirmed_group_id = False
        with self.assertRaises(UserError):
            self.config._queue(self.day)
        self.config.confirmed_group_id = self.group
        first = self.config._queue(self.day)
        second = self.config._queue(self.day)
        self.assertEqual(first, second)
        self.assertEqual(len(first.request_key), 64)
        self.assertEqual(first.state, 'queued')
        self.assertEqual(first.content, self.config.preview)

    def test_teacher_titles_and_daily_links(self):
        self.teacher.write({'teaching_title': 'mr', 'meeting_url': ' https://meet.google.com/abc-defg-hij '})
        other = self.env['edu.teacher'].create({'name': 'ZALO TEST FEMALE', 'teaching_title': 'ms',
            'meeting_url': 'https://example.zoom.us/j/123?pwd=example'})
        idle = self.env['edu.teacher'].create({'name': 'ZALO TEST IDLE', 'meeting_url': 'https://meet.google.com/idle'})
        self.env['edu.session'].create({'date': self.day, 'teacher_id': self.teacher.id,
            'time_start': 18, 'time_end': 18.5, 'attendee_ids': [(0, 0, {'student_id': self.student.id})]})
        extra = self.env['edu.session'].create({'date': self.day, 'teacher_id': other.id,
            'time_start': 19, 'time_end': 19.5, 'attendee_ids': [(0, 0, {'student_id': self.student.id})]})
        self.env['edu.session'].create({'date': self.day, 'teacher_id': self.teacher.id,
            'time_start': 21, 'time_end': 21.5, 'attendee_ids': [(0, 0, {'student_id': self.student.id})]})
        self.env['edu.session'].create({'date': self.day, 'teacher_id': idle.id,
            'state': 'cancel', 'time_start': 20, 'time_end': 20.5})
        text = self.config._schedule_text(self.day)
        self.assertTrue(text.startswith('LỊCH HỌC GVNN — 23/10/2026\n\n'))
        self.assertIn('Thầy ZALO TEST TEACHER\n17:30–18:00: ZALO TEST - STUDENT', text)
        self.assertNotIn('HỌC VIÊN:', text)
        self.assertIn('Cô ZALO TEST FEMALE\n19:00–19:30', text)
        teacher_block, teacher_link = text.split('Thầy ZALO TEST TEACHER\n', 1)[1].split('\nLINK HỌC: ', 1)
        female_block, female_link = text.split('Cô ZALO TEST FEMALE\n', 1)[1].split('\nLINK HỌC: ', 1)
        self.assertEqual(text.count('Thầy ZALO TEST TEACHER'), 1)
        for time in ('17:30–18:00', '18:00–18:30', '21:00–21:30'):
            self.assertEqual(teacher_block.splitlines().count(time + ': ZALO TEST - STUDENT'), 1)
        self.assertNotIn('\n\n', teacher_block)
        self.assertEqual(teacher_link.splitlines()[0], 'https://meet.google.com/abc-defg-hij')
        self.assertEqual(female_link.splitlines()[0], 'https://example.zoom.us/j/123?pwd=example')
        self.assertNotIn('ZALO TEST IDLE', text)
        self.assertNotIn('Lớp:', text)
        self.assertNotIn('Giờ Việt Nam |', text)
        other.meeting_url = False
        self.assertIn('Cô ZALO TEST FEMALE\n19:00–19:30: ZALO TEST - STUDENT\nLINK HỌC: CHƯA CẤU HÌNH LINK HỌC', self.config._schedule_text(self.day))
        extra.action_cancel()
        self.assertNotIn('ZALO TEST FEMALE', self.config._schedule_text(self.day))

    def test_invalid_meeting_url(self):
        for url in ('javascript:alert(1)', 'meet.google.com/abc', 'https://meet.google.com/a\nb'):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.teacher.meeting_url = url

    def test_delivery_and_ambiguous_response(self):
        message = self.config._queue(self.day)
        with patch.object(type(self.config), '_bridge', return_value={'state': 'uncertain', 'message_ids': ['partial']}):
            self.config._cron_send()
        self.assertEqual(message.state, 'uncertain')
        with self.assertRaises(UserError):
            message.action_retry()
        message.state = 'queued'
        with patch.object(type(self.config), '_bridge', return_value={'state': 'sent', 'message_ids': ['123']}) as bridge:
            self.config._cron_send()
            self.assertEqual(bridge.call_args.args[1], '/messages')
            self.assertEqual(bridge.call_args.args[2]['format'], 'schedule-v1')
        self.assertEqual(message.state, 'sent')
        self.assertEqual(message.message_ids, '123')
        with patch.object(type(self.config), '_bridge') as bridge:
            self.config._cron_send()
            bridge.assert_not_called()

    def test_transport_retry_retains_key_and_content(self):
        message = self.config._queue(self.day)
        original = (message.request_key, message.content)
        with patch.object(type(self.config), '_bridge', side_effect=UserError('offline')):
            self.config._cron_send()
        self.assertEqual(message.state, 'failed')
        message.action_retry()
        self.assertEqual(message.state, 'queued')
        self.assertEqual((message.request_key, message.content), original)

    def test_configured_hour_timezone_and_default_disabled(self):
        self.assertFalse(self.env.ref('edu_zalo.config_default').auto_send)
        self.assertEqual(self.config.send_hour, 9)
        self.config.send_hour = 12
        self.config.auto_send = True
        class BeforeNoon(datetime):
            @classmethod
            def now(cls, tz=None):
                return TZ.localize(datetime(2026, 10, 23, 11, 59))
        with patch('odoo.addons.edu_zalo.models.zalo.datetime', BeforeNoon), patch.object(type(self.config), '_bridge') as bridge:
            self.config._cron_send()
            bridge.assert_not_called()
        class AtNoon(datetime):
            @classmethod
            def now(cls, tz=None):
                return TZ.localize(datetime(2026, 10, 23, 12, 0))
        with patch('odoo.addons.edu_zalo.models.zalo.datetime', AtNoon), patch.object(type(self.config), '_bridge', return_value={'state': 'sent', 'message_ids': ['test']}):
            self.config._cron_send()
        self.assertEqual(self.config.log_ids.state, 'sent')

    def test_nine_am_window_and_validation(self):
        self.config.write({'auto_send': True, 'send_hour': 9})
        for hour, minute, expected in [(8, 59, 0), (9, 0, 1), (9, 29, 1), (9, 30, 0), (12, 0, 0)]:
            with self.subTest(hour=hour, minute=minute), self.env.cr.savepoint():
                self.config.log_ids.unlink()
                class AtTime(datetime):
                    @classmethod
                    def now(cls, tz=None):
                        return TZ.localize(datetime(2026, 10, 23, hour, minute))
                with patch('odoo.addons.edu_zalo.models.zalo.datetime', AtTime), patch.object(
                        type(self.config), '_bridge', return_value={'state': 'sent', 'message_ids': ['test']}):
                    self.config._cron_send()
                self.assertEqual(len(self.config.log_ids), expected)
        for invalid in (-1, 24):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.config.send_hour = invalid

    def test_choose_named_group_requires_confirmation(self):
        self.config.write({'auto_send': True, 'preferred_group': '  Target   Group '})
        with patch.object(type(self.config), '_bridge', return_value={
                'groups': [{'id': 'new-target', 'name': 'Target Group'}]}) as bridge:
            self.config.action_select_preferred_group()
        self.assertEqual(bridge.call_args.args, ('GET', '/groups'))
        self.assertEqual(self.config.group_id.zalo_id, 'new-target')
        self.assertEqual(self.config.confirmed_group_id, self.group)
        self.assertFalse(self.config.auto_send)
        with self.assertRaises(UserError):
            self.config._queue(self.day)
        with patch.object(type(self.config), '_bridge', return_value={}):
            self.config.action_confirm_group()
        self.assertEqual(self.config.confirmed_group_id, self.config.group_id)

    def test_choose_named_group_rejects_missing_or_duplicate(self):
        self.config.preferred_group = 'Target Group'
        for groups in ([], [{'id': 'one', 'name': 'Target Group'}, {'id': 'two', 'name': 'Target Group'}]):
            with patch.object(type(self.config), '_bridge', return_value={'groups': groups}), self.assertRaises(UserError):
                self.config.action_select_preferred_group()
        self.assertEqual(self.config.group_id, self.group)

    def test_manager_permissions_and_group_sync(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Zalo staff test', 'login': 'zalo-staff-test',
            'groups_id': [(6, 0, [self.env.ref('edu_gvnn.group_edu_staff').id])]})
        with self.assertRaises(AccessError):
            self.config.with_user(user).action_login()
        manager = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Zalo manager test', 'login': 'zalo-manager-test',
            'groups_id': [(6, 0, [self.env.ref('edu_gvnn.group_edu_manager').id])]})
        with patch.object(type(self.config), '_bridge', return_value={'groups': [{'id': 'new-test', 'name': 'Nhóm mới'}]}):
            self.config.with_user(manager)._refresh_groups()
        queued = self.config.with_user(manager)._queue(self.day)
        self.assertEqual(queued.state, 'queued')
        self.assertFalse(self.env['edu.zalo.message'].with_user(manager).check_access_rights('create', raise_exception=False))

    def test_split_long_schedule(self):
        text = '\n\n'.join(['Lịch học có dấu tiếng Việt ' * 20] * 10)
        parts = split_message(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(part) <= 1800 for part in parts))
        self.assertEqual('\n\n'.join(parts), text)

    def test_send_today_is_immediate_uses_vietnam_date_and_ignores_preview(self):
        class VietnamMidnight(datetime):
            @classmethod
            def now(cls, tz=None):
                return TZ.localize(datetime(2026, 10, 24, 0, 5))
        self.config.preview_date = '2026-10-22'
        self.env['edu.session'].create({'date': '2026-10-24', 'teacher_id': self.teacher.id,
            'time_start': 18, 'time_end': 18.5, 'attendee_ids': [(0, 0, {'student_id': self.student.id})]})
        with patch('odoo.addons.edu_zalo.models.zalo.datetime', VietnamMidnight):
            with patch.object(type(self.config), '_bridge', return_value={'state': 'sent', 'message_ids': ['direct']}) as bridge:
                result = self.config.action_send_today()
                bridge.assert_called_once()
                self.assertIn('24/10/2026', bridge.call_args.args[2]['parts'][0])
            self.assertEqual(result['tag'], 'display_notification')
            self.assertEqual(result['params']['type'], 'success')
            self.assertEqual(self.config.log_ids.date, date(2026, 10, 24))
            self.assertEqual(self.config.log_ids.state, 'sent')
            self.assertEqual(self.config.preview_date, date(2026, 10, 22))
            with patch.object(type(self.config), '_bridge', return_value={'state': 'sent', 'message_ids': ['direct-2']}) as bridge:
                result = self.config.action_send_today()
                bridge.assert_called_once()
            self.assertEqual(result['params']['type'], 'success')
            self.assertEqual(len(self.config.log_ids), 2)
            self.assertEqual(len(set(self.config.log_ids.mapped('request_key'))), 2)

    def test_direct_send_reports_failures_and_preserves_uncertain_state(self):
        class TestToday(datetime):
            @classmethod
            def now(cls, tz=None):
                return TZ.localize(datetime(2026, 10, 23, 10, 0))
        with patch('odoo.addons.edu_zalo.models.zalo.datetime', TestToday):
            with patch.object(type(self.config), '_bridge', side_effect=UserError('offline')):
                result = self.config.action_send_today()
            self.assertEqual(result['params']['type'], 'danger')
            self.assertEqual(self.config.log_ids.state, 'failed')
            with patch.object(type(self.config), '_bridge', return_value={'state': 'uncertain', 'message_ids': []}):
                result = self.config.action_send_today()
            self.assertEqual(result['params']['type'], 'warning')
            with patch.object(type(self.config), '_bridge') as bridge, self.assertRaises(UserError):
                self.config.action_send_today()
            bridge.assert_not_called()

    def test_manual_send_does_not_suppress_daily_schedule(self):
        manual = self.config._queue(self.day, manual=True)
        daily = self.config._queue(self.day)
        self.assertNotEqual(manual.request_key, daily.request_key)
        self.assertEqual(manual.send_mode, 'manual')
        self.assertEqual(daily.send_mode, 'daily')
        self.assertEqual(self.config._queue(self.day), daily)
        self.assertEqual(self.config._queue(self.day, manual=True), manual)
        manual.state = 'sent'
        self.teacher.teaching_title = 'mr'
        newer = self.config._queue(self.day, manual=True)
        self.assertNotEqual(newer, manual)
        self.assertIn('Thầy ZALO TEST TEACHER', newer.content)
        self.assertEqual(self.config._queue(self.day), daily)

    def test_list_button_delegates_without_selected_sessions_and_checks_permissions(self):
        with patch.object(type(self.config), 'action_send_today', return_value={'tag': 'display_notification'}) as send:
            self.assertEqual(self.env['edu.session'].action_send_today_zalo()['tag'], 'display_notification')
            send.assert_called_once()
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Zalo list staff test', 'login': 'zalo-list-staff-test',
            'groups_id': [(6, 0, [self.env.ref('edu_gvnn.group_edu_staff').id])]})
        with patch.object(type(self.config), '_bridge') as bridge, self.assertRaises(AccessError):
            self.env['edu.session'].with_user(user).action_send_today_zalo()
        bridge.assert_not_called()
