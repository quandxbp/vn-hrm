import base64
import io
import zipfile
from datetime import datetime
from xml.etree import ElementTree as ET

import xlrd

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


@tagged('post_install', '-at_install')
class TestExportWeek(TransactionCase):
    def setUp(self):
        super().setUp()
        self.week = self.env['edu.week'].create({
            'number': 99881, 'date_from': '2042-05-05', 'date_to': '2042-05-11'})
        self.teacher = self.env['edu.teacher'].create({'name': 'Weekly Export Teacher'})
        self.students = self.env['edu.student'].create([
            {'name_vi': 'Export Alpha', 'name_en': 'Alpha'},
            {'name_vi': 'Export Beta', 'name_en': 'Beta'},
        ])

    def session(self, **values):
        return self.env['edu.session'].create({
            'date': self.week.date_from, 'teacher_id': self.teacher.id,
            'time_start': 20.5, 'time_end': 21,
            'attendee_ids': [(0, 0, {'student_id': student.id, 'score': 9 - index})
                             for index, student in enumerate(self.students)], **values,
        })

    def export(self):
        wizard = self.env['edu.export.week.wizard'].create({'week_id': self.week.id})
        action = wizard.action_export()
        self.assertIn('download=true', action['url'])
        archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(wizard.file)))
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        self.assertEqual([s.attrib['name'] for s in workbook.findall('m:sheets/m:sheet', NS)], ['Weekly'])
        strings = ET.fromstring(archive.read('xl/sharedStrings.xml'))
        strings = [''.join(s.itertext()) for s in strings]
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        cells = {}
        for cell in sheet.findall('m:sheetData/m:row/m:c', NS):
            value = cell.find('m:v', NS)
            if value is not None:
                cells[cell.attrib['r']] = strings[int(value.text)] if cell.attrib.get('t') == 's' else float(value.text)
        return cells, sheet

    def test_weekly_columns_and_data_are_in_template_positions(self):
        session = self.session(youtube_url='https://youtu.be/weekly12345',
                               google_drive_url='https://drive.google.com/file/d/weekly123/view')
        session.write({'minutes': 60, 'student_hours': 1, 'teacher_hours': .5})
        cells, sheet = self.export()
        self.assertEqual(sheet.find('m:dimension', NS).attrib['ref'], 'A1:AB2')
        self.assertEqual(cells['A1'], 'NO')
        self.assertEqual(cells['P1'], 'VIDEO ON PADLET\nKHUÊ ĐÃ GẮN LINK LÊN PADLET GHI "1"')
        self.assertEqual(cells['Q1'], '\nJOINED:"1"\nCANCED:"0"')
        self.assertEqual(cells['AB1'], 'SCORE STUDENT 3')
        self.assertEqual(cells['B2'], self.week.number)
        self.assertEqual(cells['F2'], self.teacher.name)
        self.assertEqual(cells['G2'], self.students[0].name)
        self.assertEqual(cells['H2'], self.students[1].name)
        self.assertEqual(xlrd.xldate_as_datetime(cells['D2'], 0), datetime(2042, 5, 5))
        self.assertAlmostEqual(cells['K2'] * 24, 20.5)
        self.assertEqual((cells['M2'], cells['N2'], cells['O2']), (60, 1, .5))
        self.assertEqual(cells['Q2'], 1)
        self.assertEqual(cells['W2'], 1)
        self.assertEqual(cells['X2'], session.youtube_url)
        self.assertEqual(cells['Y2'], session.google_drive_url)
        self.assertEqual([link.attrib['ref'] for link in sheet.findall('m:hyperlinks/m:hyperlink', NS)], ['X2', 'Y2'])
        self.assertEqual((cells['Z2'], cells['AA2']), (9, 8))
        for col in ('P', 'R', 'S', 'V', 'AB'):
            self.assertNotIn(col + '2', cells)

    def test_cancelled_absence_notes_and_literal_text(self):
        session = self.session(state='cancel', note='=1+1', completion_note='Teacher unavailable')
        session.attendee_ids[1].present = False
        cells, sheet = self.export()
        self.assertEqual(cells['Q2'], 0)
        self.assertIn(self.students[1].name, cells['T2'])
        self.assertIn('Teacher unavailable', cells['T2'])
        self.assertEqual(cells['U2'], '=1+1')
        self.assertFalse(sheet.findall('.//m:f', NS))
        self.assertEqual(cells['H2'], self.students[1].name)

    def test_legacy_link_and_unknown_times_are_not_fabricated(self):
        session = self.session(time_start=0, time_end=0,
                               recording_url='https://youtu.be/legacy12345', video_posted=True)
        cells, _sheet = self.export()
        self.assertEqual(cells['X2'], session.recording_url)
        self.assertEqual(cells['W2'], 1)
        for col in ('K', 'L', 'V', 'Y'):
            self.assertNotIn(col + '2', cells)
        session.google_drive_url = session.recording_url
        links, _posted = self.env['edu.export.week.wizard']._weekly_video_values(session)
        self.assertEqual(links, [session.recording_url, ''])

    def test_empty_week_has_clear_error(self):
        wizard = self.env['edu.export.week.wizard'].create({'week_id': self.week.id})
        with self.assertRaises(UserError):
            wizard.action_export()
