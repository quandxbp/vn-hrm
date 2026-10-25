# -*- coding: utf-8 -*-
import base64
import re
from collections import Counter, defaultdict
from datetime import date as Date, timedelta
from types import SimpleNamespace

import xlrd

from odoo import fields, models
from odoo.exceptions import UserError

from ..tools import get_param, normalize_name, youtube_recording_url

SHEET_ATT = '2.ĐIỂM DANH'
SHEET_FEE = '4. THU HỌC PHÍ GVNN'
SHEET_TRACK = '3.THEO DÕI HỌC SINH'
SHEET_CAT = 'DANH MỤC'
TEACHER_ALIASES = {'LURICH': 'LUIRICH'}
BATCH = 200
_STATES = {}  # Bộ nhớ tạm theo lần chạy: recordset không cho gán thuộc tính mới.


def _text(value):
    return value.strip() if isinstance(value, str) else ('' if value in (None, '') else str(value))


def _num(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class EduImportWizard(models.TransientModel):
    _name = 'edu.import.wizard'
    _description = 'Import dữ liệu từ file TỔNG HỢP_GVNN.xlsx'

    file = fields.Binary('File Excel', required=True)
    filename = fields.Char('Tên file')
    import_mode = fields.Selection([
        ('attendance', 'Lịch sử buổi học — sheet 2.ĐIỂM DANH'),
        ('all', 'Nhập dữ liệu tổng hợp (nâng cao)'),
    ], string='Chế độ nhập', required=True, default='attendance')
    date_from = fields.Date('Từ ngày', help='Để trống để lấy từ đầu lịch sử trong file.')
    date_to = fields.Date('Đến ngày', help='Để trống để import đến hết dữ liệu.')
    agency_id = fields.Many2one(
        'res.partner', 'Agency của giáo viên mới', domain=[('is_company', '=', True)],
        help='Giáo viên chưa có trong hệ thống được tạo là giáo viên qua Agency này. Để trống thì tạo là giáo viên trực tiếp.')
    import_catalog = fields.Boolean('Giáo viên và lịch sử đơn giá', default=True)
    import_students = fields.Boolean('Học viên', default=True)
    set_opening = fields.Boolean('Đặt số dư đầu kỳ cho học viên', default=True)
    import_payments = fields.Boolean('Thu học phí', default=True)
    import_sessions = fields.Boolean('Buổi học (điểm danh)', default=True)
    create_periods = fields.Boolean('Tạo kỳ lương cho các tháng đã qua', default=True)
    result = fields.Text('Kết quả', readonly=True)

    # ---------- đọc file ----------
    def _attendance_sheet(self, book):
        expected = re.sub(r'\s+', '', SHEET_ATT).casefold()
        for name in book.sheet_names():
            if re.sub(r'\s+', '', name).casefold() == expected:
                return book.sheet_by_name(name)
        raise UserError('Không tìm thấy sheet 2.ĐIỂM DANH trong file Excel.')

    def _date(self, book, value):
        if isinstance(value, str):
            # Một số ô trong file gốc lưu ngày dạng chữ, ví dụ "28/7/2026" (ngày/tháng/năm).
            match = re.match(r'^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$', value)
            try:
                return Date(int(match.group(3)), int(match.group(2)), int(match.group(1))) if match else False
            except ValueError:
                return False
        number = _num(value)
        if not number or number <= 0:
            return False
        return xlrd.xldate_as_datetime(number, book.datemode).date()

    def _hour(self, value):
        number = _num(value)
        if number is None or not 0 <= number < 1:
            return 0.0
        return round(number * 24 * 60) / 60.0

    def _in_range(self, date):
        return bool(date) and (not self.date_from or date >= self.date_from) and (not self.date_to or date <= self.date_to)

    def _read_fee_rows(self, book):
        sheet = book.sheet_by_name(SHEET_FEE)
        months = {c: self._date(book, sheet.cell_value(1, c)) for c in range(5, 30)}
        rows = []
        for r in range(2, sheet.nrows):
            v = sheet.row_values(r)
            name_vi = normalize_name(_text(v[1]))
            if not name_vi:
                continue
            name_en = normalize_name(_text(v[2]))
            rows.append({
                'name_vi': name_vi, 'name_en': name_en,
                'name': ' - '.join(p for p in (name_vi, name_en) if p),
                'code': _text(v[36]), 'studying': _num(v[34]) == 1.0,
                'payments': {months[c]: _num(v[c]) for c in months if months[c] and _num(v[c])},
                'excel_balance': _num(v[32]) or 0.0,
            })
        return rows

    def _read_zalo(self, book):
        sheet = book.sheet_by_name(SHEET_TRACK)
        return {normalize_name(_text(sheet.cell_value(r, 3))): _text(sheet.cell_value(r, 5))
                for r in range(2, sheet.nrows) if _text(sheet.cell_value(r, 3)) and _text(sheet.cell_value(r, 5))}

    def _read_sessions(self, book):
        sheet = self._attendance_sheet(book)
        rows = []
        for r in range(2, sheet.nrows):
            v = sheet.row_values(r) + [''] * 30
            date = self._date(book, v[3])
            if not date:
                continue
            teacher = normalize_name(_text(v[5]))
            rows.append({
                'row': r + 1,
                'stt': int(v[0]) if _num(v[0]) else None,
                'week': int(v[1]) if _num(v[1]) else None,
                'date': date, 'text_date': isinstance(v[3], str),
                'teacher': TEACHER_ALIASES.get(teacher, teacher),
                'students': [normalize_name(_text(x)) for x in v[6:9] if _text(x)],
                'classes': [normalize_name(c) for c in re.split(r'\+', _text(v[9])) if c.strip()],
                'start': self._hour(v[10]), 'end': self._hour(v[11]),
                'minutes': _num(v[12]), 'student_hours': _num(v[13]), 'teacher_hours': _num(v[14]),
                'state': _text(v[15]),
                'notes': [_text(x) for x in v[16:19]],
                'extras': [_text(x) for x in v[19:22]],
                'score': _num(v[22]), 'scores': [_num(x) for x in v[22:24]],
            })
        return rows

    # ---------- danh mục ----------
    def _st(self):
        return _STATES[self.id]

    def _teacher(self, name, log):
        name = TEACHER_ALIASES.get(name, name)
        teacher = self._st().teachers.get(name)
        if not teacher and name:
            teacher = self.env['edu.teacher'].create({
                'name': name, 'teacher_type': 'agency' if self.agency_id else 'direct',
                'agency_id': self.agency_id.id or False})
            self._st().teachers[name] = teacher
            log.append('Tạo giáo viên mới: %s' % name)
        return teacher

    def _import_catalog(self, book, rows, log):
        sheet = book.sheet_by_name(SHEET_CAT)
        names = {normalize_name(_text(sheet.cell_value(r, 1))) for r in range(1, sheet.nrows)}
        names |= {normalize_name(_text(sheet.cell_value(r, 8))) for r in range(1, sheet.nrows)}
        names |= {r['teacher'] for r in rows}
        for name in sorted(n for n in names if n):
            self._teacher(name, log)
        created = 0
        Rate = self.env['edu.teacher.rate']
        for r in range(1, sheet.nrows):
            name = TEACHER_ALIASES.get(normalize_name(_text(sheet.cell_value(r, 8))), normalize_name(_text(sheet.cell_value(r, 8))))
            date, rate = self._date(book, sheet.cell_value(r, 9)), _num(sheet.cell_value(r, 10))
            teacher = self._st().teachers.get(name)
            if not (teacher and date and rate):
                continue
            if not Rate.search_count([('teacher_id', '=', teacher.id), ('date_from', '=', date)]):
                Rate.create({'teacher_id': teacher.id, 'date_from': date, 'rate': rate})
                created += 1
        log.append('Đơn giá: tạo %s dòng mới.' % created)

    # ---------- học viên ----------
    def _import_students(self, book, fee_rows, log):
        zalo = self._read_zalo(book)
        Student = self.env['edu.student'].with_context(active_test=False)
        created = 0
        max_code = 0
        for row in fee_rows:
            student = self._st().students.get(row['name'])
            if not student:
                code = row['code'] if row['code'] and not Student.search_count([('code', '=', row['code'])]) else False
                vals = {'name_vi': row['name_vi'], 'name_en': row['name_en'] or False,
                        'state': 'studying' if row['studying'] else 'stopped',
                        'zalo_group': zalo.get(row['name']) or False}
                if code:
                    vals['code'] = code
                student = Student.create(vals)
                self._st().students[row['name']] = student
                created += 1
            match = re.match(r'HV(\d+)$', student.code or '')
            max_code = max(max_code, int(match.group(1)) if match else 0)
        seq = self.env['ir.sequence'].search([('code', '=', 'edu.student')], limit=1)
        if seq and seq.number_next_actual <= max_code:
            seq.number_next_actual = max_code + 1
        log.append('Học viên: tạo %s, đã có %s.' % (created, len(fee_rows) - created))

    def _set_openings(self, fee_rows, rows, log):
        block_minutes = get_param(self.env, 'block_minutes', 30.0) or 30.0
        price = get_param(self.env, 'block_price', 100000.0)
        learned = defaultdict(float)
        for row in rows:
            if row['date'] < self.date_from:
                hours = row['student_hours'] or 0.0
                for name in row['students']:
                    learned[name] += hours
        changed = 0
        for item in fee_rows:
            student = self._st().students.get(item['name'])
            if not student:
                continue
            if student.opening_date and student.opening_date <= self.date_from:
                continue
            paid = sum(v for d, v in item['payments'].items() if d < self.date_from)
            balance = paid - learned[item['name']] * 60.0 / block_minutes * price
            student.write({'opening_date': self.date_from, 'opening_balance': balance})
            changed += 1
        log.append('Số dư đầu kỳ (tại %s): đặt cho %s học viên.' % (self.date_from, changed))

    # ---------- thu học phí ----------
    def _import_payments(self, fee_rows, log):
        Pay = self.env['edu.tuition.payment']
        price = get_param(self.env, 'block_price', 100000.0) or 100000.0
        created = skipped = missing = 0
        for item in fee_rows:
            student = self._st().students.get(item['name'])
            if not student:
                missing += 1
                continue
            for date, amount in sorted(item['payments'].items()):
                if not self._in_range(date):
                    continue
                key = '%s-%s' % (student.code, date.strftime('%Y-%m'))
                if Pay.search_count([('import_key', '=', key)]):
                    skipped += 1
                    continue
                Pay.create({
                    'student_id': student.id, 'date': date, 'import_key': key,
                    'payment_type': 'refund' if amount < 0 else 'payment',
                    'gross_amount': abs(amount), 'blocks': abs(amount) / price, 'block_price': price,
                    'method': 'other', 'note': 'Import từ Excel'})
                created += 1
        log.append('Thu học phí: tạo %s phiếu, bỏ qua %s phiếu đã import.' % (created, skipped)
                   + (' Không tìm thấy %s học viên.' % missing if missing else ''))

    # ---------- buổi học ----------
    def _weeks(self, rows, log):
        Week = self.env['edu.week']
        by_number = defaultdict(list)
        for row in rows:
            if row['week']:
                by_number[row['week']].append(row['date'])
        result = {}
        for number, dates in sorted(by_number.items()):
            week = Week.search([('number', '=', number)], limit=1)
            if not week:
                monday = (self._st().history_mondays[number] if self.import_mode == 'attendance'
                          else min(dates) - timedelta(days=min(dates).weekday()))
                try:
                    with self.env.cr.savepoint():
                        week = Week.create({'number': number, 'date_from': monday,
                                            'date_to': monday + timedelta(days=6)})
                except Exception as exc:  # noqa
                    log.append('Không tạo được tuần %s: %s' % (number, exc))
                    continue
            result[number] = week
        return result

    def _class(self, name):
        cls = self._st().classes.get(name)
        if not cls:
            cls = self.env['edu.class'].create({'name': name})
            self._st().classes[name] = cls
        return cls

    def _key(self, row):
        """Khoá import của một dòng điểm danh: STT, kèm số dòng nếu STT bị trùng trong file."""
        if not row['stt']:
            return 'xlsx-row%s' % row['row']
        if self._st().stt_counts[row['stt']] > 1:
            return 'xlsx-%s-r%s' % (row['stt'], row['row'])
        return 'xlsx-%s' % row['stt']

    def _parse_session(self, row, log):
        """Chuyển một dòng điểm danh thành giá trị tạo `edu.session`; trả về None nếu bỏ qua."""
        if not row['teacher']:
            log.append('Dòng %s bỏ qua: thiếu giáo viên.' % row['row'])
            return None
        if self.import_mode == 'attendance' and row['week']:
            week = self._st().week_map.get(row['week'])
            if not week or not week.date_from <= row['date'] <= week.date_to:
                log.append('Dòng %s bỏ qua: ngày %s không khớp khoảng ngày của tuần %s. '
                           'Hãy kiểm tra lại ngày và số tuần trong Excel.' % (row['row'], row['date'], row['week']))
                return None
        teacher = self._teacher(row['teacher'], log)
        state_text = row['state'].upper()
        note_text = ' '.join(row['notes']).upper()
        cancel = 'CANCEL' in state_text or 'CANCEL' in note_text
        students = self._st().students
        marker = next((s for s in row['students'] if s not in students and (
            re.match(r'(TESTING|SPEAKING)', s) or ' - ' not in s)), None)
        testing = bool(marker) or any(k in state_text + ' ' + note_text for k in ('DEMO', 'TEST'))
        notes = [n for n in row['notes'] if n and n not in ('1', '1.0')]
        recording = next((x for x in row['extras'] if x.startswith('http')), False)
        video_posted = _text(row['extras'][1]).upper() in ('OK', '0K', 'ỌK')
        minutes = row['minutes'] or ((row['student_hours'] or 0.5) * 60)
        vals = {
            'date': row['date'], 'teacher_id': teacher.id, 'time_start': row['start'], 'time_end': row['end'],
            'minutes': minutes, 'student_hours': row['student_hours'] or 0.0,
            'teacher_hours': row['teacher_hours'] or 0.0,
            'state': 'cancel' if cancel else 'done',
            'completion_note': row['state'][:100] or False, 'note': ' | '.join(notes) or False,
            'recording_url': recording, 'video_posted': video_posted,
            'import_key': self._key(row),
        }
        if youtube_recording_url(recording):
            vals['youtube_url'] = youtube_recording_url(recording)
        week = self._st().week_map.get(row['week'])
        if week:
            vals['week_id'] = week.id
        extra = []
        if testing:
            name = re.sub(r'^(TESTING|SPEAKING)\s*(TEST|PRACTICE)?\s*-?\s*', '', marker or '').strip()
            class_names = [name] if name else (row['classes'] or ['GVNN'])
            vals.update(session_type='testing', class_ids=[(6, 0, [self._class(c).id for c in class_names])])
            if row['students'] and not marker:
                notes.append('Học viên: ' + ', '.join(row['students']))
                vals['note'] = ' | '.join(notes)
            return vals, [], []
        only = re.search(r'ONLY\s+([^)]+)', state_text)
        only_names = {normalize_name(n) for n in re.split(r'[,&]|\bAND\b', only.group(1))} if only else None
        attendees = []
        seen = set()
        for name in row['students']:
            student = self._st().students.get(name)
            if not student:
                extra.append(name)
                continue
            if student.id in seen:
                continue
            seen.add(student.id)
            present = True
            if only_names is not None:
                english = normalize_name(student.name_en or '')
                present = english in only_names or normalize_name(student.name_vi) in only_names
            attendees.append((0, 0, {
                'student_id': student.id, 'present': present,
                'score': int(row.get('scores', [row['score']])[len(attendees)] or 0)
                         if len(attendees) < len(row.get('scores', [row['score']])) else 0}))
        if only_names is not None and attendees and not any(a[2]['present'] for a in attendees):
            for att in attendees:
                att[2]['present'] = True
            log.append('Dòng %s: "%s" không khớp học viên nào, coi tất cả có mặt.' % (row['row'], row['state']))
        if extra:
            vals['extra_participants'] = ', '.join(extra)
        classes = [c for c in row['classes'] if c] or ['GVNN']
        vals['class_ids'] = [(6, 0, [self._class(c).id for c in classes])]
        vals['attendee_ids'] = attendees
        return vals, extra, [s for s in seen]

    def _import_sessions(self, rows, log):
        Session = self.env['edu.session'].with_context(tracking_disable=True)
        wanted = [r for r in rows if self._in_range(r['date'])]
        text_dates = [r['row'] for r in wanted if r['text_date']]
        if text_dates:
            log.append('Có %s dòng điểm danh lưu ngày dạng chữ (ví dụ dòng %s), đã đọc thành ngày/tháng/năm.' % (
                len(text_dates), text_dates[0]))
        self._st().week_map = self._weeks(wanted, log)
        existing = set(Session.search([('import_key', '!=', False)]).mapped('import_key'))
        created = skipped = failed = 0
        unmatched = defaultdict(int)
        class_links = defaultdict(set)
        batch = []

        def flush_batch():
            nonlocal created, failed
            if not batch:
                return
            try:
                with self.env.cr.savepoint():
                    Session.create([b[0] for b in batch])
                created += len(batch)
            except Exception:
                for vals, row in batch:
                    try:
                        with self.env.cr.savepoint():
                            Session.create(vals)
                        created += 1
                    except Exception as exc:  # noqa
                        failed += 1
                        log.append('Dòng %s lỗi: %s' % (row['row'], str(exc).splitlines()[0][:120]))
            batch.clear()

        for row in wanted:
            key = self._key(row)
            if key in existing:
                skipped += 1
                continue
            parsed = self._parse_session(row, log)
            if not parsed:
                failed += 1
                continue
            vals, extra, _ = parsed
            for name in extra:
                unmatched[name] += 1
            if vals.get('session_type') != 'testing':
                for att in vals['attendee_ids']:
                    for cname in row['classes']:
                        if cname != 'GVNN':
                            class_links[att[2]['student_id']].add(self._class(cname).id)
            batch.append((vals, row))
            existing.add(key)
            if len(batch) >= BATCH:
                flush_batch()
        flush_batch()
        for student_id, class_ids in class_links.items():
            self.env['edu.student'].browse(student_id).write({'class_ids': [(4, c) for c in class_ids]})
        log.append('Buổi học: tạo %s, bỏ qua %s đã import, lỗi hoặc bỏ qua %s.' % (created, skipped, failed))
        if unmatched:
            log.append('Tên học viên không khớp (%s tên, đưa vào "Người tham gia khác"): %s' % (
                len(unmatched), ', '.join('%s (%s)' % kv for kv in sorted(unmatched.items())[:20])))

    def _create_periods(self, log):
        Period = self.env['edu.payroll.period']
        today = fields.Date.context_today(self)
        month = self.date_from.replace(day=1)
        last = min(self.date_to or today, today).replace(day=1)
        created = 0
        while month < last:
            if not Period.search_count([('date_from', '=', month)]):
                Period.create({'date_from': month})
                created += 1
            month = (month + timedelta(days=32)).replace(day=1)
        log.append('Kỳ lương: tạo %s kỳ (trạng thái đang mở, hãy đối chiếu rồi chốt).' % created)

    def _reconcile(self, fee_rows, log):
        diffs = []
        for item in fee_rows:
            student = self._st().students.get(item['name'])
            if student and student.state == 'studying':
                diffs.append((abs(student.balance - item['excel_balance']), student.name, student.balance, item['excel_balance']))
        diffs.sort(reverse=True)
        bad = [d for d in diffs if d[0] > 1000]
        log.append('Đối chiếu số dư với Excel (học viên đang học): %s/%s lệch hơn 1.000 đ.' % (len(bad), len(diffs)))
        for d in bad[:10]:
            log.append('  %s: hệ thống %s, Excel %s' % (d[1], '{:,.0f}'.format(d[2]), '{:,.0f}'.format(d[3])))

    # ---------- chạy ----------
    def action_import(self):
        self.ensure_one()
        if not self.env.user.has_group('edu_gvnn.group_edu_manager'):
            raise UserError('Chỉ quản lý được nhập dữ liệu buổi học.')
        # Serialize imports so concurrent clicks/files cannot create the same catalogue twice.
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s)', [60706261])
        self.invalidate_recordset(['result'])
        if self.result:
            return self._result_action()
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise UserError('Ngày kết thúc phải sau ngày bắt đầu.')
        if self.import_mode == 'all' and not self.date_from:
            raise UserError('Chọn ngày bắt đầu khi nhập dữ liệu tổng hợp.')
        try:
            book = xlrd.open_workbook(file_contents=base64.b64decode(self.file))
            self._attendance_sheet(book)
        except UserError:
            raise
        except Exception as exc:  # noqa
            raise UserError('Không đọc được file Excel, hãy chọn đúng file TỔNG HỢP_GVNN.xlsx (%s).' % exc)
        log = ['Nhập lịch sử từ %s%s' % (self.date_from or 'đầu file', ' đến %s' % self.date_to if self.date_to else '')]
        session_rows = self._read_sessions(book)
        if not any(self._in_range(row['date']) for row in session_rows):
            raise UserError('Không có buổi học hợp lệ trong khoảng ngày đã chọn.')
        fee_rows = self._read_fee_rows(book) if self.import_mode == 'all' else []
        history_dates = defaultdict(Counter)
        for row in session_rows:
            if row['week']:
                history_dates[row['week']][row['date'] - timedelta(days=row['date'].weekday())] += 1
        _STATES[self.id] = SimpleNamespace(
            teachers={t.name: t for t in self.env['edu.teacher'].with_context(active_test=False).search([])},
            students={s.name: s for s in self.env['edu.student'].with_context(active_test=False).search([])},
            classes={c.name: c for c in self.env['edu.class'].with_context(active_test=False).search([])},
            week_map={}, stt_counts=Counter(r['stt'] for r in session_rows if r['stt']),
            history_mondays={number: counts.most_common(1)[0][0] for number, counts in history_dates.items()})
        try:
            if self.import_mode == 'attendance':
                self._prepare_history_students(session_rows, log)
                self._import_sessions(session_rows, log)
                self.result = '\n'.join(log)
                return self._result_action()
            return self._run_import(book, log, session_rows, fee_rows)
        finally:
            _STATES.pop(self.id, None)

    def _prepare_history_students(self, rows, log):
        created = 0
        for row in rows:
            if not self._in_range(row['date']) or not row['teacher']:
                continue
            if any(word in (row['state'] + ' ' + ' '.join(row['notes'])).upper() for word in ('DEMO', 'TEST')):
                continue
            for name in row['students']:
                if name in self._st().students or re.match(r'^(TESTING|SPEAKING)\b', name):
                    continue
                parts = name.rsplit(' - ', 1)
                student = self.env['edu.student'].create({
                    'name_vi': parts[0], 'name_en': parts[1] if len(parts) > 1 else False,
                    'state': 'stopped',
                    'note': 'Tạo khi nhập lịch sử buổi học từ Excel.',
                })
                self._st().students[name] = student
                created += 1
        log.append('Học viên còn thiếu trong lịch sử: tạo %s.' % created)

    def _result_action(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}

    def _run_import(self, book, log, session_rows, fee_rows):
        if self.import_catalog:
            self._import_catalog(book, session_rows, log)
        if self.import_students:
            self._import_students(book, fee_rows, log)
        if self.set_opening:
            self._set_openings(fee_rows, session_rows, log)
        if self.import_payments:
            self._import_payments(fee_rows, log)
        if self.import_sessions:
            self._import_sessions(session_rows, log)
        if self.create_periods and self.import_sessions:
            self._create_periods(log)
        if self.import_students and self.import_payments and self.import_sessions and self.set_opening:
            self.env.flush_all()
            self._reconcile(fee_rows, log)
        self.result = '\n'.join(log)
        return self._result_action()
