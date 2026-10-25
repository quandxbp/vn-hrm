import base64
import io
from datetime import datetime

import xlsxwriter

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..wizard.edu_import_wizard import _STATES


@tagged('post_install', '-at_install')
class TestImportHistory(TransactionCase):
    def workbook(self, rows=None, sheet='2.Điểm danh'):
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {'in_memory': True})
        ws = book.add_worksheet(sheet)
        ws.write_row(1, 0, ['STT', 'TUẦN', 'THỨ', 'NGÀY'])
        for index, changes in enumerate(rows or [{}], start=2):
            values = {0: 985001 + index, 1: 98501, 3: datetime(2001, 1, 1),
                      5: 'History Teacher', 6: 'History Alpha - Alex', 7: 'History Beta - Bob',
                      9: 'History Class', 10: 20.5 / 24, 11: 21 / 24,
                      12: 30, 13: .5, 14: .5, 15: 'done',
                      19: 'https://youtu.be/history1234', 20: 'OK', 22: 9, 23: 8}
            values.update(changes)
            for col, value in values.items():
                if isinstance(value, datetime):
                    ws.write_datetime(index, col, value, book.add_format({'num_format': 'dd/mm/yyyy'}))
                elif value is not None:
                    ws.write(index, col, value)
        book.close()
        return base64.b64encode(buf.getvalue())

    def wizard(self, **values):
        return self.env['edu.import.wizard'].create({'file': self.workbook(), **values})

    def imported(self):
        return self.env['edu.session'].search([('import_key', 'like', 'xlsx-985%')])

    def test_attendance_sheet_only_and_old_dates(self):
        before = {model: self.env[model].search_count([]) for model in
                  ['edu.tuition.payment', 'edu.payroll.period', 'edu.teacher.rate']}
        wizard = self.wizard()
        self.assertFalse(wizard.date_from)
        wizard.action_import()
        session = self.imported()
        self.assertEqual(len(session), 1)
        self.assertEqual(str(session.date), '2001-01-01')
        self.assertEqual(session.week_id.number, 98501)
        self.assertEqual(session.attendee_ids.mapped('score'), [9, 8])
        self.assertEqual(session.youtube_url, 'https://youtu.be/history1234')
        self.assertEqual(session.attendee_ids.mapped('student_id.state'), ['stopped', 'stopped'])
        for model, count in before.items():
            self.assertEqual(self.env[model].search_count([]), count)
        self.assertNotIn(wizard.id, _STATES)

    def test_repeat_file_and_repeat_button_do_not_duplicate(self):
        wizard = self.wizard()
        wizard.action_import()
        wizard.action_import()
        self.wizard().action_import()
        self.assertEqual(len(self.imported()), 1)

    def test_date_filter_does_not_create_excluded_students(self):
        wizard = self.wizard(file=self.workbook([{}, {0: 985010, 3: datetime(2001, 1, 2),
                                                      6: 'Excluded Student - Skip'}]),
                             date_from='2001-01-01', date_to='2001-01-01')
        wizard.action_import()
        self.assertEqual(len(self.imported()), 1)
        self.assertFalse(self.env['edu.student'].search_count([('name_en', '=', 'SKIP')]))

    def test_cancelled_and_testing_rows(self):
        wizard = self.wizard(file=self.workbook([
            {15: 'CANCELED'},
            {0: 985010, 6: 'TESTING HISTORY CLASS', 7: None, 15: 'SPEAKING TEST'},
        ]))
        wizard.action_import()
        sessions = self.imported()
        self.assertEqual(len(sessions), 2)
        self.assertEqual(len(sessions.filtered(lambda s: s.state == 'cancel')), 1)
        testing = sessions.filtered(lambda s: s.session_type == 'testing')
        self.assertEqual(len(testing), 1)
        self.assertFalse(testing.attendee_ids)

    def test_outlier_week_date_is_reported(self):
        wizard = self.wizard(file=self.workbook([{}, {0: 985010},
                                                {0: 985011, 3: datetime(2001, 2, 1)}]))
        wizard.action_import()
        self.assertEqual(len(self.imported()), 2)
        self.assertIn('không khớp', wizard.result)

    def test_missing_sheet_and_empty_range_have_clear_errors(self):
        with self.assertRaisesRegex(UserError, 'Không tìm thấy sheet'):
            self.wizard(file=self.workbook(sheet='Other')).action_import()
        with self.assertRaisesRegex(UserError, 'Không có buổi học'):
            self.wizard(date_from='2002-01-01').action_import()
