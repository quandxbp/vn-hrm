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
Teacher = env['edu.teacher']
Session = env['edu.session']
Period = env['edu.payroll.period']
agency = env['res.partner'].create({'name': 'AGENCY T4', 'is_company': True})
ta = Teacher.create({'name': 'T4AGENCY', 'teacher_type': 'agency', 'agency_id': agency.id})
td = Teacher.create({'name': 'T4DIRECT', 'teacher_type': 'direct'})
tn = Teacher.create({'name': 'T4NORATE', 'teacher_type': 'direct'})
env['edu.teacher.rate'].create({'teacher_id': ta.id, 'date_from': '2025-01-01', 'rate': 200000})
env['edu.teacher.rate'].create({'teacher_id': td.id, 'date_from': '2025-01-01', 'rate': 150000})
s1 = env['edu.student'].create({'name_vi': 'T4 Mot', 'name_en': 'One'})
s2 = env['edu.student'].create({'name_vi': 'T4 Hai', 'name_en': 'Two'})
cls = env['edu.class'].create({'name': 'T4CLASS'})


def mk(teacher, date, start, end, students=(), **kw):
    vals = {'teacher_id': teacher.id, 'date': date, 'time_start': start, 'time_end': end}
    if students:
        vals['attendee_ids'] = [(0, 0, {'student_id': s.id}) for s in students]
    vals.update(kw)
    return Session.create(vals)


a1 = mk(ta, '2025-05-05', 19, 20, [s1])
a2 = mk(ta, '2025-05-12', 19, 20.5, [s1, s2])
a_cancel = mk(ta, '2025-05-13', 19, 20, [s1])
a_cancel.action_cancel()
a_test = mk(ta, '2025-05-14', 19, 19.5, session_type='testing', class_ids=[(6, 0, [cls.id])])
d1 = mk(td, '2025-05-06', 8, 9, [s2])
d_absent = mk(td, '2025-05-07', 8, 9, [s2])
d_absent.attendee_ids.action_toggle_present()
n1 = mk(tn, '2025-05-08', 8, 9, [s1])
jun = mk(td, '2025-06-03', 8, 9, [s2])

chk('period_id trong khi chua co ky', not a1.sudo().period_id and not a1.locked)

p = Period.create({'date_from': '2025-05-01'})
chk('ten ky', p.name == 'Lương 05/2025', p.name)
chk('date_to', str(p.date_to) == '2025-05-31', p.date_to)
chk('period_id gan', a1.sudo().period_id == p and not a1.locked)
lines = {l.teacher_id.name: l for l in p.line_ids}
chk('3 GV co dong', set(lines) == {'T4AGENCY', 'T4DIRECT', 'T4NORATE'}, list(lines))
la = lines['T4AGENCY']
chk('agency 3 buoi', la.session_count == 3, la.session_count)
chk('agency 3h', abs(la.hours - 3.0) < 1e-6, la.hours)
chk('agency 600k', la.amount == 600000, la.amount)
chk('agency rate cuoi thang', la.rate_end_month == 200000, la.rate_end_month)
ld = lines['T4DIRECT']
chk('direct 1 buoi (vang khong tinh)', ld.session_count == 1 and ld.amount == 150000, (ld.session_count, ld.amount))
chk('direct khong lan thang 6', abs(ld.hours - 1.0) < 1e-6, ld.hours)
chk('cancel khong tinh', a_cancel.paid_hours == 0)
ln = lines['T4NORATE']
chk('khong don gia -> no_rate', ln.status == 'no_rate', ln.status)
chk('tong ky', p.total_amount == 600000 + 150000, p.total_amount)

la.write({'agency_hours': 3.0, 'agency_amount': 600000})
chk('agency khop -> ok', la.status == 'ok', la.status)
la.write({'agency_hours': 3.5, 'agency_amount': 700000})
chk('agency lech -> agency_diff', la.status == 'agency_diff', la.status)
chk('lech gio/tien', abs(la.diff_hours - 0.5) < 1e-6 and la.diff_amount == 100000, (la.diff_hours, la.diff_amount))
la.write({'agency_hours': 3.0, 'agency_amount': 600000})

b = mk(td, '2025-05-20', 8, 9, [s1])
p.action_compute()
chk('tinh lai them buoi', lines['T4DIRECT'].session_count == 2 and lines['T4DIRECT'].amount == 300000)
b.unlink()
p.action_compute()
chk('tinh lai bot buoi', lines['T4DIRECT'].session_count == 1)

staff = env['res.users'].create({'name': 'staff t4', 'login': 'staff_t4', 'groups_id': [(6, 0, [env.ref('edu_gvnn.group_edu_staff').id])]})
mgr = env['res.users'].create({'name': 'mgr t4', 'login': 'mgr_t4', 'groups_id': [(6, 0, [env.ref('edu_gvnn.group_edu_manager').id])]})
chk('giao vu khong chot', raises(lambda: p.with_user(staff).action_lock(), AccessError))
p.with_user(mgr).action_lock()
chk('da chot', p.state == 'locked' and p.locked_by == mgr, (p.state, p.locked_by.name))
chk('buoi paid', all(s.paid for s in (a1, a2, a_cancel, a_test, d1, d_absent, n1)) and not jun.paid)
chk('locked flag', a1.locked and not jun.locked)

chk('khong tao buoi thang da chot', raises(lambda: mk(td, '2025-05-25', 8, 9, [s1]), UserError))
chk('khong sua buoi da chot', raises(lambda: a1.write({'time_end': 21}), UserError))
chk('khong xoa buoi da chot', raises(lambda: a1.unlink(), UserError))
chk('khong chuyen buoi vao thang chot', raises(lambda: jun.write({'date': '2025-05-28'}), UserError))
chk('khong them HV vao buoi chot', raises(lambda: env['edu.session.attendee'].create({'session_id': a1.id, 'student_id': s2.id}), UserError))
chk('khong doi HV buoi chot', raises(lambda: a1.attendee_ids.action_toggle_present(), UserError))
chk('khong xoa HV buoi chot', raises(lambda: a1.attendee_ids.unlink(), UserError))
chk('khong nghi buoi da chot', raises(lambda: a1.action_cancel(), UserError))
chk('khong tinh lai ky chot', raises(lambda: p.action_compute(), UserError))
chk('khong xoa ky chot', raises(lambda: p.unlink(), UserError))
chk('sua buoi thang 6 van duoc', not raises(lambda: jun.write({'time_end': 10})))

Rate = env['edu.teacher.rate']
chk('khong them gia hieu luc trong thang chot', raises(lambda: Rate.create({'teacher_id': td.id, 'date_from': '2025-05-15', 'rate': 1}), UserError))
rate_td = td.rate_ids[0]
chk('khong sua gia da dung', raises(lambda: rate_td.write({'rate': 1}), UserError))
r6 = Rate.create({'teacher_id': td.id, 'date_from': '2025-06-01', 'rate': 180000})
chk('them gia tu thang chua chot ok', bool(r6.id))
chk('buoi thang 6 lay gia moi', jun.sudo().teacher_rate == 180000, jun.sudo().teacher_rate)
chk('buoi thang 5 giu gia cu', d1.sudo().teacher_rate == 150000, d1.sudo().teacher_rate)

chk('manager khong mo khoa', raises(lambda: p.with_user(mgr).action_unlock(), AccessError))
chk('giao vu khong mo khoa', raises(lambda: p.with_user(staff).action_unlock(), AccessError))
p.action_unlock()
chk('admin mo khoa', p.state == 'open' and not p.locked_by and not a1.paid and not a1.locked)
chk('log mo khoa', any('mở khoá' in (m.body or '') for m in p.message_ids))
chk('sua duoc sau mo khoa', not raises(lambda: a1.write({'note': 'x'})))
p.action_lock()
chk('chot lai', p.state == 'locked' and a1.paid)

chk('trung thang bi chan', raises(lambda: Period.create({'date_from': '2025-05-01'})))
chk('khong phai ngay 1', raises(lambda: Period.create({'date_from': '2025-07-15'})))

html = env['ir.actions.report']._render_qweb_html('edu_gvnn.report_payroll_agency', p.ids)[0].decode()
chk('doi soat: co GV agency, khong co GV truc tiep', 'T4AGENCY' in html and 'T4DIRECT' not in html)
chk('doi soat: co ten agency', 'AGENCY T4' in html)
html = env['ir.actions.report']._render_qweb_html('edu_gvnn.report_payroll_direct', p.ids)[0].decode()
chk('luong truc tiep: co T4DIRECT, khong co agency', 'T4DIRECT' in html and 'T4AGENCY' not in html)
try:
    pdf, _ = env['ir.actions.report']._render_qweb_pdf('edu_gvnn.report_payroll_agency', p.ids)
    chk('render pdf', pdf[:4] == b'%PDF', pdf[:8])
except Exception as e:
    chk('render pdf', False, repr(e)[:200])

for n, ok, extra in res:
    print('PASS' if ok else 'FAIL', n, extra if not ok else '')
print('TOTAL', sum(1 for r in res if r[1]), '/', len(res))
env.cr.rollback()
env['ir.sequence'].search([('code', 'in', ['edu.student', 'edu.tuition.payment', 'edu.tuition.refund'])]).write({'number_next_actual': 1})
env.cr.commit()
