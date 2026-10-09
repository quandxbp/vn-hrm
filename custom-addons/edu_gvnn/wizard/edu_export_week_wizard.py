# -*- coding: utf-8 -*-
import base64
import io

import xlsxwriter

from odoo import fields, models
from odoo.exceptions import UserError

HEADERS = [
    'STT', 'TUẦN', 'THỨ TRONG TUẦN', 'NGÀY', 'THÁNG', 'GIÁO VIÊN', 'HỌC VIÊN 1', 'HỌC VIÊN 2',
    'HỌC VIÊN 3', 'LỚP', 'GIỜ BẮT ĐẦU', 'GIỜ KẾT THÚC', 'PHÚT', 'GIỜ TÍNH CHO HỌC VIÊN',
    'GIỜ TÍNH CHO GIÁO VIÊN', 'STATE OF COMPLETION', 'NOTE - KHUÊ', 'NOTE - KIM', 'NOTE - TIÊN',
    'RECORDINGS', 'POSTED VIDEO', 'PAID', 'SCORE STUDENT 1', 'SCORE STUDENT 2',
]
# Cột AH, AI của sheet gốc; các cột Y..AG để trống để dán thẳng vào file Excel cũ.
MONTH_COL, YEAR_COL = 33, 34


class EduExportWeekWizard(models.TransientModel):
    _name = 'edu.export.week.wizard'
    _description = 'Xuất điểm danh theo tuần ra Excel'

    week_id = fields.Many2one(
        'edu.week', 'Tuần', required=True,
        default=lambda self: self.env['edu.week.alert']._default_week())
    file = fields.Binary('File', readonly=True)
    filename = fields.Char('Tên file', readonly=True)

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

    def action_export(self):
        self.ensure_one()
        sessions = self.env['edu.session'].search(
            [('week_id', '=', self.week_id.id)], order='date, time_start, id')
        if not sessions:
            raise UserError('Tuần này chưa có buổi học nào.')
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        ws = wb.add_worksheet('2.ĐIỂM DANH')
        head = wb.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'bg_color': '#D9E1F2', 'border': 1})
        date_fmt = wb.add_format({'num_format': 'dd/mm/yyyy'})
        time_fmt = wb.add_format({'num_format': 'hh:mm'})
        for col, title in enumerate(HEADERS):
            ws.write(1, col, title, head)
        ws.write(1, MONTH_COL, 'THÁNG', head)
        ws.write(1, YEAR_COL, 'NĂM', head)
        ws.set_row(1, 32)
        ws.set_column(0, 1, 7)
        ws.set_column(3, 3, 12)
        ws.set_column(5, 8, 22)
        ws.set_column(9, 9, 16)
        ws.set_column(15, 15, 24)
        ws.freeze_panes(2, 0)

        for index, session in enumerate(sessions, start=1):
            row = index + 1
            attendees = session.attendee_ids
            if session.session_type == 'testing':
                students = ['TESTING ' + ' + '.join(session.class_ids.mapped('name'))]
            else:
                students = [a.student_id.name for a in attendees]
            students += [''] * (3 - len(students))
            has_time = bool(session.time_start or session.time_end)
            scores = [a.score or '' for a in attendees][:2] + ['', '']
            values = [
                index, session.week_id.number, session.weekday, None, session.date.month,
                session.teacher_id.name, students[0], students[1], students[2],
                ' + '.join(session.class_ids.mapped('name')) or 'GVNN', None, None, session.minutes,
                session.student_hours, session.teacher_hours, self._completion_text(session),
                session.note or '', '', '', session.recording_url or '',
                'OK' if session.video_posted else '', 1 if session.paid else '', scores[0], scores[1],
            ]
            for col, value in enumerate(values):
                if value not in (None, ''):
                    ws.write(row, col, value)
            ws.write_datetime(row, 3, fields.Datetime.to_datetime(session.date), date_fmt)
            if has_time:
                ws.write_number(row, 10, (session.time_start % 24) / 24.0, time_fmt)
                ws.write_number(row, 11, (session.time_end % 24) / 24.0, time_fmt)
            ws.write_number(row, MONTH_COL, session.date.month)
            ws.write_number(row, YEAR_COL, session.date.year)
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
