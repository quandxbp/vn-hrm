from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import Form
res = []
def chk(name, cond, extra=''):
    res.append((name, bool(cond), extra))

env = env(context=dict(env.context, tracking_disable=True))
Student = env['edu.student']; Pay = env['edu.tuition.payment']
Teacher = env['edu.teacher']; Session = env['edu.session']

s = Student.create({'name_vi': 'Test Ba', 'name_en': 'Tom', 'parent_name': 'Me Ba'})
# default phiếu thu: 20 buổi = 2.000.000
f = Form(Pay)
f.student_id = s
chk('mac dinh 20 buoi', f.blocks == 20, f.blocks)
chk('mac dinh 2tr', f.gross_amount == 2000000, f.gross_amount)
chk('payer tu phu huynh', f.payer_name == 'Me Ba', f.payer_name)
f.blocks = 10
chk('doi so buoi -> tien', f.gross_amount == 1000000, f.gross_amount)
f.gross_amount = 1500000
chk('nhap tien -> so buoi', f.blocks == 15, f.blocks)
p1 = f.save()
chk('amount = gross', p1.amount == 1500000, p1.amount)
chk('ref PT', p1.ref.startswith('PT'), p1.ref)
chk('bang chu', 'đồng' in (p1.amount_text or '').lower(), p1.amount_text)

p2 = Pay.create({'student_id': s.id, 'blocks': 10, 'block_price': 100000, 'gross_amount': 1000000, 'discount_amount': 100000})
chk('giam gia', p2.amount == 900000, p2.amount)
try:
    with env.cr.savepoint():
        Pay.create({'student_id': s.id, 'gross_amount': 1000, 'discount_amount': 2000})
    chk('giam gia > thanh tien bi chan', False)
except Exception as e:
    chk('giam gia > thanh tien bi chan', True)

chk('so du sau thu', s.total_paid == 2400000 and s.balance == 2400000, (s.total_paid, s.balance))
chk('con lai 24 buoi', abs(s.remaining_blocks - 24) < 1e-6, s.remaining_blocks)
chk('khong canh bao', not s.fee_warning, s.fee_warning)

# hoàn tiền
r = Pay.create({'student_id': s.id, 'payment_type': 'refund', 'gross_amount': 400000, 'blocks': 4, 'block_price': 100000})
chk('refund am', r.amount == -400000, r.amount)
chk('ref PC', r.ref.startswith('PC'), r.ref)
chk('so du sau hoan', s.balance == 2000000, s.balance)

# trừ học phí qua buổi học
t = Teacher.create({'name': 'TESTTEACH', 'teacher_type': 'direct'})
sess = Session.create({'teacher_id': t.id, 'date': '2026-03-02', 'time_start': 19.0, 'time_end': 20.0,
                       'attendee_ids': [(0, 0, {'student_id': s.id})]})
chk('tru 1h = 2 buoi = 200k', s.learned_amount == 200000 and s.balance == 1800000, (s.learned_amount, s.balance))
sess.attendee_ids.action_toggle_present()
chk('vang khong tru', s.learned_amount == 0 and s.balance == 2000000, (s.learned_amount, s.balance))
sess.attendee_ids.action_toggle_present()
chk('last_session_date', str(s.last_session_date) == '2026-03-02', s.last_session_date)

# cảnh báo học phí
s2 = Student.create({'name_vi': 'Test Hai', 'name_en': 'Bob'})
chk('khong thu -> out', s2.fee_warning == 'out', s2.fee_warning)
Pay.create({'student_id': s2.id, 'gross_amount': 250000, 'blocks': 2.5, 'block_price': 100000})
chk('250k -> low', s2.fee_warning == 'low', s2.fee_warning)
Pay.create({'student_id': s2.id, 'gross_amount': 500000, 'blocks': 5, 'block_price': 100000})
chk('750k -> khong', not s2.fee_warning, s2.fee_warning)
s2.action_stop()
chk('ngung hoc -> khong canh bao', not s2.fee_warning)

# số dư đầu kỳ
s3 = Student.create({'name_vi': 'Test Ba3', 'opening_date': '2026-01-01', 'opening_balance': 500000})
Pay.create({'student_id': s3.id, 'date': '2025-12-01', 'gross_amount': 999999, 'blocks': 1, 'block_price': 1})
Pay.create({'student_id': s3.id, 'date': '2026-01-05', 'gross_amount': 100000, 'blocks': 1, 'block_price': 100000})
chk('opening bo qua phieu cu', s3.balance == 600000, s3.balance)

# quyền
staff = env['res.users'].create({'name': 'staff t', 'login': 'staff_t3', 'groups_id': [(6, 0, [env.ref('edu_gvnn.group_edu_staff').id, env.ref('base.group_user').id])]})
try:
    Pay.with_user(staff).create({'student_id': s.id, 'payment_type': 'refund', 'gross_amount': 1000})
    chk('giao vu khong hoan tien', False)
except AccessError:
    chk('giao vu khong hoan tien', True)
try:
    pp = Pay.with_user(staff).create({'student_id': s.id, 'gross_amount': 100000, 'blocks': 1, 'block_price': 100000})
    chk('giao vu tao phieu thu', True)
except Exception as e:
    chk('giao vu tao phieu thu', False, e)

# in phiếu
for rec in (p1, r):
    html = env['ir.actions.report']._render_qweb_html('edu_gvnn.report_tuition_receipt', rec.ids)[0].decode()
    chk('in %s' % rec.ref, ('PHIẾU CHI' if rec.payment_type == 'refund' else 'PHIẾU THU') in html and rec.ref in html)

for n, ok, extra in res:
    print('PASS' if ok else 'FAIL', n, extra if not ok else '')
print('TOTAL', sum(1 for r in res if r[1]), '/', len(res))
env.cr.rollback()
env['ir.sequence'].search([('code', '=', 'edu.student')]).write({'number_next_actual': 1})
env.cr.commit()
