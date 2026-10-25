# -*- coding: utf-8 -*-
import base64
import io

import xlsxwriter

from odoo import fields, models
from odoo.exceptions import UserError
from ..tools import youtube_recording_url

HEADERS = [
    'NO', 'WEEK', 'DAY OF WEEK', 'DATE', 'MONTH', 'TEACHER',
    'STUDENT 1', 'STUDENT 2', 'STUDENT 3', 'GRADE', 'START TIME ', 'END TIME',
    'DURATION (MINUTES)', ' (HOUR) FOR STUDENT', ' (HOUR) FOR TEACHER',
    'VIDEO ON PADLET\nKHUÊ ĐÃ GẮN LINK LÊN PADLET GHI "1"',
    '\nJOINED:"1"\nCANCED:"0"',
    'HOMEWORK  ON PADLET\nGV ĐÃ POST HW GHI 1 \nKHUÊ QUẢN LÝ',
    'HỌC SINH ĐÃ HOÀN THÀNH BÀI TRÊN PADLET ', 'NOTE ', 'NOTE (Quân)',
    'THỜI LƯỢNG ', 'IS POSTED VIDEOS?', 'LINK VIDEO 1', 'LINK VIDEO 2',
    'SCORE STUDENT 1', 'SCORE STUDENT 2', 'SCORE STUDENT 3',
]


class EduExportWeekWizard(models.TransientModel):
    _name = 'edu.export.week.wizard'
    _description = 'Xuất điểm danh theo tuần ra Excel'

    week_id = fields.Many2one(
        'edu.week', 'Tuần', required=True,
        default=lambda self: self.env['edu.week.alert']._default_week())
    file = fields.Binary('File', readonly=True)
    filename = fields.Char('Tên file', readonly=True)

    def _video_values(self, session):
        return (session.youtube_url or session.google_drive_url or session.recording_url or '',
                'OK' if session.youtube_url or session.video_posted else '')

    def _completion_text(self, session):
        if session.state == 'cancel':
            return 'CANCELED'
        text = session.completion_note or 'done'
        absent = session.attendee_ids.filtered(lambda a: not a.present)
        if absent:
            present = session.attendee_ids - absent
            names = ', '.join((a.student_id.name_en or a.student_id.name_vi).title() for a in present)
            text += ' (only %s)' % names if names else ' (no one attended)'
        return text

    def _weekly_video_values(self, session):
        parts = session._recording_parts()
        if len(parts) > 1:
            youtube_links = [p['youtube'] for p in parts if p['youtube']]
            drive_links = [p['drive'] for p in parts if p['drive']]
            posted = 1 if all(p['youtube'] for p in parts) else ''
            return (['\n'.join(youtube_links), '\n'.join(drive_links)] if youtube_links else
                    [drive_links[0] if drive_links else '', '\n'.join(drive_links[1:])]), posted
        youtube = (session.youtube_url or youtube_recording_url(session.recording_url) or '').strip()
        links = []
        for link in (youtube, session.google_drive_url, session.recording_url):
            link = (link or '').strip()
            if link and link not in links:
                links.append(link)
        return (links + ['', ''])[:2], 1 if youtube or session.video_posted else ''

    def _weekly_note(self, session):
        notes = [session.completion_note] if session.completion_note else []
        absent = session.attendee_ids.filtered(lambda attendee: not attendee.present)
        if absent:
            notes.append('Vắng: ' + ', '.join(absent.mapped('student_id.name')))
        return '\n'.join(notes)

    def action_export(self):
        self.ensure_one()
        sessions = self.env['edu.session'].search(
            [('week_id', '=', self.week_id.id)], order='date, time_start, id')
        if not sessions:
            raise UserError('Tuần này chưa có buổi học nào.')
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True, 'strings_to_formulas': False})
        ws = wb.add_worksheet('Weekly')
        head = wb.add_format({'bold': True, 'text_wrap': True, 'valign': 'vcenter',
                              'align': 'center', 'bg_color': '#D9E1F2', 'border': 1, 'font_size': 10})
        body = wb.add_format({'valign': 'top', 'font_size': 10})
        note_fmt = wb.add_format({'valign': 'top', 'text_wrap': True, 'font_size': 10})
        date_fmt = wb.add_format({'num_format': 'dd/mm/yyyy', 'valign': 'top', 'font_size': 10})
        time_fmt = wb.add_format({'num_format': 'hh:mm', 'valign': 'top', 'font_size': 10})
        hours_fmt = wb.add_format({'num_format': '0.00', 'valign': 'top', 'font_size': 10})
        for col, title in enumerate(HEADERS):
            ws.write_string(0, col, title, head)
        ws.set_row(0, 60)
        ws.set_column(0, 0, 5, body)
        ws.set_column(1, 1, 7, body)
        ws.set_column(2, 2, 12, body)
        ws.set_column(3, 3, 12)
        ws.set_column(4, 4, 9, body)
        ws.set_column(5, 5, 15, body)
        ws.set_column(6, 8, 28, body)
        ws.set_column(9, 9, 26, body)
        ws.set_column(10, 11, 11)
        ws.set_column(12, 14, 13, body)
        ws.set_column(15, 15, 20, body, {'hidden': True})
        ws.set_column(16, 16, 15, body, {'hidden': True})
        ws.set_column(17, 17, 36, body, {'hidden': True})
        ws.set_column(18, 18, 17, body, {'hidden': True})
        ws.set_column(19, 20, 30, note_fmt)
        ws.set_column(21, 21, 13, body)
        ws.set_column(22, 22, 16, body)
        ws.set_column(23, 24, 40, body)
        ws.set_column(25, 27, 12, body)
        ws.freeze_panes(1, 6)
        ws.autofilter(0, 0, len(sessions), len(HEADERS) - 1)

        for index, session in enumerate(sessions, start=1):
            row = index
            attendees = session.attendee_ids
            if session.session_type == 'testing':
                students = ['TESTING ' + ' + '.join(session.class_ids.mapped('name'))]
            else:
                students = [a.student_id.name for a in attendees]
            if session.extra_participants:
                students.append(session.extra_participants)
            students += [''] * (3 - len(students))
            has_time = bool(session.time_start or session.time_end)
            scores = [a.score or '' for a in attendees][:3] + ['', '', '']
            video_links, video_posted = self._weekly_video_values(session)
            if any('\n' in link for link in video_links):
                ws.set_row(row, max(30, 15 * max(link.count('\n') + 1 for link in video_links)))
            values = [
                index, session.week_id.number, session.weekday, None, session.date.month,
                session.teacher_id.name, students[0], students[1], students[2],
                ' + '.join(session.class_ids.mapped('name')) or 'GVNN', None, None, session.minutes,
                session.student_hours, session.teacher_hours,
                '', 1 if session.state == 'done' else 0, '', '',
                self._weekly_note(session), session.note or '',
                '', video_posted, video_links[0], video_links[1], scores[0], scores[1], scores[2],
            ]
            for col, value in enumerate(values):
                if value not in (None, ''):
                    if col in (23, 24) and '\n' in str(value):
                        ws.write_string(row, col, value, note_fmt)
                    else:
                        ws.write(row, col, value, hours_fmt if col in (13, 14) else note_fmt if col in (19, 20) else body)
            ws.write_datetime(row, 3, fields.Datetime.to_datetime(session.date), date_fmt)
            if has_time:
                ws.write_number(row, 10, (session.time_start % 24) / 24.0, time_fmt)
                ws.write_number(row, 11, (session.time_end % 24) / 24.0, time_fmt)
        wb.close()
        self.write({
            'file': base64.b64encode(buf.getvalue()),
            'filename': 'diem-danh-tuan-%s.xlsx' % self.week_id.number,
        })
        return {
            'type': 'ir.actions.act_url', 'target': 'self',
            'url': '/web/content/?model=%s&id=%s&field=file&filename_field=filename&download=true'
                   % (self._name, self.id),
        }
