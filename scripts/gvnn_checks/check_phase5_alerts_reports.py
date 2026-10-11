import base64

import xlrd

from odoo.exceptions import AccessError, UserError

res = []


def chk(name, cond, extra=''):
    res.append((name, bool(cond), extra))


def raises(fn, exc=Exception):
    try:
        with env.cr.savepoint():
            fn()
        return False
    except exc:
        return True


env = env(context=dict(env.context, tracking_disable=True))
Week = env['edu.week']
Alert = env['edu.week.alert']
Session = env['edu.session']
Pay = env['edu.tuition.payment']

# 6 tuần liên tiếp, số tuần 101..106, tuần 106 bắt đầu 2025-04-07
weeks = {}
from datetime import date, timedelta
start = date(2025, 3, 3)
for i in range(6):
    weeks[101 + i] = Week.create({
        'number': 101 + i, 'date_from': start + timedelta(days=7 * i),
        'date_to': start + timedelta(days=7 * i + 6)})
W = weeks[106]

teacher = env['edu.teacher'].create({'name': 'T5TEACH', 'teacher_type': 'direct'})
env['edu.teacher.rate'].create({'teacher_id': teacher.id, 'date_from': '2025-01-01', 'rate': 100000})
cls = env['edu.class'].create({'name': 'T5CLASS'})


def student(code, en, paid=5000000, state='studying'):
    s = env['edu.student'].create({'name_vi': 'T5 ' + code, 'name_en': en})
    if paid:
        Pay.create({'student_id': s.id, 'date': '2025-03-01', 'gross_amount': paid,
                    'blocks': paid / 100000.0, 'block_price': 100000})
    if state == 'stopped':
        s.action_stop()
    return s


def lesson(week_no, s, day_offset=0, present=True, hours=1.0):
    d = weeks[week_no].date_from + timedelta(days=day_offset)
    sess = Session.create({
        'teacher_id': teacher.id, 'date': d, 'time_start': 19.0, 'time_end': 19.0 + hours,
        'attendee_ids': [(0, 0, {'student_id': s.id, 'present': present})]})
    return sess


A = student('A', 'Amy')
B = student('B', 'Ben')
C = student('C', 'Cat')
D = student('D', 'Dan')
E = student('E', 'Eve', paid=0)
F = student('F', 'Fay', paid=250000)
G = student('G', 'Gus', state='stopped')
H = student('H', 'Hal')

lesson(106, A)
lesson(106, A, 2)
lesson(105, B)
lesson(103, C)
lesson(102, D)
lesson(106, E, hours=0.5)
lesson(106, F, hours=0.5)
lesson(106, H, present=False)
lesson(105, H)
# buổi testing và buổi nghỉ trong tuần 106 không được tính là đi học
Session.create({'teacher_id': teacher.id, 'date': W.date_from, 'time_start': 8, 'time_end': 9,
                'session_type': 'testing', 'class_ids': [(6, 0, [cls.id])]})
cancelled = lesson(106, B, 3)
cancelled.action_cancel()

alerts = Alert._generate(W)
by = {a.student_id: a for a in alerts}
chk('G (ngung hoc) khong co canh bao', G not in by)
chk('co canh bao cho HV dang hoc', {A, B, C, D, E, F, H} <= set(by) and len(by) == len(env['edu.student'].search([('state', '=', 'studying')])),
    (len(by),))
a = by[A]
chk('A: gio tuan = 2, 2 buoi', a.hours_n0 == 2 and a.session_count == 2, (a.hours_n0, a.session_count))
chk('A: on', a.priority == 'ok' and not a.absent and a.action == 'Không cần xử lý', (a.priority, a.action))
b = by[B]
chk('B: nghi tuan nay (buoi huy khong tinh), N-1 = 1', b.absent and b.hours_n0 == 0 and b.hours_n1 == 1, (b.absent, b.hours_n0, b.hours_n1))
chk('B: vang, streak 1', b.priority == 'yellow' and b.absent_streak == 1 and not b.absent_3w, (b.priority, b.absent_streak))
c = by[C]
chk('C: nghi 3 tuan -> red_now', c.priority == 'red_now' and c.absent_3w and c.absent_streak == 3, (c.priority, c.absent_streak))
chk('C: chua de xuat ngung', not c.suggest_stop)
chk('C: hanh dong goi phu huynh', 'Gọi phụ huynh' in c.action, c.action)
d = by[D]
chk('D: nghi 4 tuan -> de xuat ngung', d.suggest_stop and d.absent_3w and d.priority == 'red_now', (d.suggest_stop, d.absent_streak))
e = by[E]
chk('E: het hoc phi -> do', e.priority == 'red' and e.fee_warning == 'out', (e.priority, e.fee_warning))
chk('E: balance am', e.balance == -100000, e.balance)
f = by[F]
chk('F: gan het hoc phi -> vang', f.priority == 'yellow' and f.fee_warning == 'low', (f.priority, f.fee_warning))
h = by[H]
chk('H: vang mat khong tinh gio', h.absent and h.hours_n0 == 0 and h.hours_n1 == 1, (h.absent, h.hours_n0, h.hours_n1))
chk('thu tu: red_now truoc', alerts[0].priority == 'red_now', [x.priority for x in alerts])

# chạy lại không trùng, giữ ghi chú liên hệ
c.write({'contacted': True, 'contact_note': 'da goi'})
n = len(alerts)
alerts2 = Alert._generate(W)
chk('chay lai khong trung', len(alerts2) == n and Alert.search_count([('week_id', '=', W.id)]) == n)
chk('giu ghi chu lien he', by[C].contacted and by[C].contact_note == 'da goi')

# nút Ngưng học trên dòng cảnh báo
by[D].action_stop_student()
chk('ngung hoc tu canh bao', D.state == 'stopped')
Alert._generate(W)
chk('HV ngung bi bo khoi canh bao', not Alert.search([('week_id', '=', W.id), ('student_id', '=', D.id)]))
# chu ky tuan truoc khong anh huong
prev = Alert._generate(weeks[105])
chk('tuan 105: B khong nghi', not {x.student_id: x for x in prev}[B].absent)

# wizard và quyền
staff = env['res.users'].create({'name': 'staff t5', 'login': 'staff_t5', 'groups_id': [(6, 0, [env.ref('edu_gvnn.group_edu_staff').id])]})
mgr = env['res.users'].create({'name': 'mgr t5', 'login': 'mgr_t5', 'groups_id': [(6, 0, [env.ref('edu_gvnn.group_edu_manager').id])]})
wiz = env['edu.week.alert.wizard'].with_user(staff).create({'week_id': W.id})
act = wiz.action_generate()
chk('giao vu chay wizard canh bao', act.get('res_model') == 'edu.week.alert' and Alert.search_count([('week_id', '=', W.id)]) > 0)
al = Alert.with_user(staff).search([('week_id', '=', W.id)], limit=1)
chk('giao vu ghi chu lien he', not raises(lambda: al.write({'contacted': True, 'contact_note': 'x'})))
chk('default week', bool(Alert._default_week()))

# chi phí khác
Cat = env['edu.expense.category']
chk('co danh muc chi phi san', Cat.search_count([]) >= 6, Cat.search_count([]))
Exp = env['edu.other.expense']
chk('giao vu khong tao chi phi', raises(lambda: Exp.with_user(staff).create({'name': 'x', 'category_id': Cat.search([], limit=1).id, 'amount': 1}), AccessError))
chk('chi phi am bi chan', raises(lambda: Exp.create({'name': 'x', 'category_id': Cat.search([], limit=1).id, 'amount': -1})))
Exp.create({'date': '2025-03-10', 'name': 'Zoom', 'category_id': Cat.search([], limit=1).id, 'amount': 300000})
Exp.create({'date': '2025-03-20', 'name': 'Ads', 'category_id': Cat.search([], limit=1).id, 'amount': 200000})

# báo cáo tài chính
env.flush_all()
Fin = env['edu.report.finance'].with_user(mgr)
dom = [('date', '>=', '2025-03-01'), ('date', '<=', '2025-04-30')]
g = Fin.read_group(dom, ['income', 'revenue', 'salary', 'other_expense', 'total_cost', 'cash_flow'], [])[0]
pays = Pay.search([('date', '>=', '2025-03-01'), ('date', '<=', '2025-04-30')])
sess = Session.search([('date', '>=', '2025-03-01'), ('date', '<=', '2025-04-30')])
att = env['edu.session.attendee'].search([('date', '>=', '2025-03-01'), ('date', '<=', '2025-04-30')])
exp_income = sum(pays.mapped('amount'))
exp_salary = sum(sess.sudo().mapped('teacher_amount'))
exp_rev = sum(att.mapped('charge_amount'))
chk('tai chinh: thu', g['income'] == exp_income, (g['income'], exp_income))
chk('tai chinh: luong', g['salary'] == exp_salary and exp_salary > 0, (g['salary'], exp_salary))
chk('tai chinh: doanh thu ghi nhan', g['revenue'] == exp_rev and exp_rev > 0, (g['revenue'], exp_rev))
chk('tai chinh: chi phi khac', g['other_expense'] == 500000, g['other_expense'])
chk('tai chinh: tong chi', g['total_cost'] == exp_salary + 500000, g['total_cost'])
chk('tai chinh: dong tien', g['cash_flow'] == exp_income - exp_salary - 500000, g['cash_flow'])
chk('giao vu khong xem bao cao tai chinh', raises(lambda: env['edu.report.finance'].with_user(staff).search([]), AccessError))
m = Fin.read_group(dom, ['income', 'salary'], ['date:month'])
chk('nhom theo thang', len(m) == 2, [x['date:month'] for x in m])

# export xlsx
sess_w = Session.search([('week_id', '=', W.id)], order='date, time_start, id')
x = env['edu.export.week.wizard'].with_user(staff).create({'week_id': W.id})
x.action_export()
book = xlrd.open_workbook(file_contents=base64.b64decode(x.file))
chk('xlsx 1 sheet ten dung', book.sheet_names() == ['2.ĐIỂM DANH'], book.sheet_names())
sh = book.sheet_by_index(0)
head = [sh.cell_value(1, c) for c in range(sh.ncols)]
chk('tieu de cot', head[0] == 'STT' and head[1] == 'TUẦN' and head[5] == 'GIÁO VIÊN' and head[6] == 'HỌC VIÊN 1' and head[15] == 'STATE OF COMPLETION', head[:16])
chk('cot THANG/NAM o cuoi', sh.cell_value(1, 33) == 'THÁNG' and sh.cell_value(1, 34) == 'NĂM')
chk('so dong = so buoi', sh.nrows - 2 == len(sess_w), (sh.nrows - 2, len(sess_w)))
rows = [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(2, sh.nrows)]
chk('tuan = 106, GV dung', all(r[1] == 106 and r[5] == 'T5TEACH' for r in rows))
chk('buoi testing ghi TESTING <lop>', any(r[6] == 'TESTING T5CLASS' for r in rows))
chk('buoi nghi ghi CANCELED', any(r[15] == 'CANCELED' for r in rows))
chk('HV vang ghi only', any('no one attended' in str(r[15]) for r in rows), [r[15] for r in rows])
chk('ten HV dang Viet - Anh', any(r[6] == 'T5 A - AMY' for r in rows), [r[6] for r in rows])
chk('ngay la so serial', all(isinstance(r[3], float) and r[3] > 40000 for r in rows))
chk('gio bat dau', any(abs(r[10] - 19 / 24.0) < 1e-6 for r in rows))
chk('thang/nam', all(r[33] in (3, 4) and r[34] == 2025 for r in rows))
empty = env['edu.export.week.wizard'].create({'week_id': weeks[101].id})
chk('tuan trong bi chan', raises(lambda: empty.action_export(), UserError))

for n_, ok, extra in res:
    print('PASS' if ok else 'FAIL', n_, extra if not ok else '')
print('TOTAL', sum(1 for r in res if r[1]), '/', len(res))
env.cr.rollback()
env['ir.sequence'].search([('code', 'in', ['edu.student', 'edu.tuition.payment', 'edu.tuition.refund'])]).write({'number_next_actual': 1})
env.cr.commit()
