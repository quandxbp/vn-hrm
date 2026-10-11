import base64
import time
from collections import defaultdict

t0 = time.time()
env = env(context=dict(env.context, tracking_disable=True))
with open('/tmp/gvnn.xlsx', 'rb') as fh:
    data = base64.b64encode(fh.read())

wiz = env['edu.import.wizard'].create({'file': data, 'filename': 'gvnn.xlsx', 'date_from': '2026-01-01'})
try:
    wiz.action_import()
except Exception as exc:
    import traceback
    print('IMPORT_FAILED', repr(exc)[:500])
    traceback.print_exc()
    env.cr.rollback()
    raise SystemExit(1)
print('IMPORT_SECONDS', round(time.time() - t0, 1))
print('=== LOG ===')
print(wiz.result)
print('=== END LOG ===')

env.flush_all()
cr = env.cr


def one(sql, *args):
    cr.execute(sql, args)
    return cr.fetchone()[0]


print('REPORT students_total', one('select count(*) from edu_student'))
print('REPORT students_studying', one("select count(*) from edu_student where state='studying'"))
print('REPORT sessions', one('select count(*) from edu_session'))
print('REPORT sessions_cancel', one("select count(*) from edu_session where state='cancel'"))
print('REPORT sessions_testing', one("select count(*) from edu_session where session_type='testing'"))
print('REPORT payments', one('select count(*) from edu_tuition_payment'))
print('REPORT teachers', one('select count(*) from edu_teacher'))
print('REPORT classes', one('select count(*) from edu_class'))
print('REPORT weeks', one('select count(*) from edu_week'))
print('REPORT periods', one('select count(*) from edu_payroll_period'))
print('REPORT thu_2026 (excel 292,898,333)', one("select coalesce(sum(amount),0) from edu_tuition_payment where date>='2026-01-01' and date<'2027-01-01'"))
print('REPORT luong_2026 (excel 130,939,708)', one("select coalesce(sum(teacher_amount),0) from edu_session where date>='2026-01-01' and date<'2027-01-01'"))
print('REPORT gio_gv_2026 (excel 1069.075)', one("select coalesce(sum(paid_hours),0) from edu_session where date>='2026-01-01' and date<'2027-01-01'"))
print('REPORT buoi_2026 (excel 2227)', one("select count(*) from edu_session where date>='2026-01-01' and date<'2027-01-01'"))
print('REPORT buoi_tinh_luong_2026', one("select count(*) from edu_session where paid_hours>0 and date>='2026-01-01' and date<'2027-01-01'"))
print('REPORT so_du_HV_dang_hoc (excel 60,918,333)', one("select coalesce(sum(balance),0) from edu_student where state='studying'"))
print('REPORT cong_no_du_kien (excel 64,091,666)', one("select coalesce(sum(balance),0) from edu_student where state='studying' and balance>0"))
cr.execute("""select to_char(date,'MM'), count(*), coalesce(sum(teacher_amount),0)
              from edu_session where date>='2026-01-01' and date<'2027-01-01' group by 1 order by 1""")
excel = {'01': 20942750, '02': 9108625, '03': 18577500, '04': 16049583, '05': 19080000,
         '06': 10925833, '07': 13997500, '08': 14311667, '09': 7946250}
for m, n, amt in cr.fetchall():
    print('MONTH %s sessions=%s salary=%s excel=%s diff=%s' % (m, n, amt, excel.get(m), (amt - excel[m]) if m in excel else None))
cr.execute("""select t.name, count(*), round(sum(s.paid_hours)::numeric,2), sum(s.teacher_amount)
              from edu_session s join edu_teacher t on t.id=s.teacher_id
              where s.date>='2026-01-01' group by 1 order by 1""")
for row in cr.fetchall():
    print('TEACHER', row)
cr.execute("select name, teacher_type from edu_teacher order by name")
print('TEACHERS_ALL', cr.fetchall())
cr.execute("select warning, count(*) from edu_session where state='done' group by 1 order by 1")
print('WARNINGS', cr.fetchall())
cr.execute("select name from edu_class order by name")
print('CLASSES', [r[0] for r in cr.fetchall()][:60])

# chay lai lan 2: khong duoc tao them ban ghi
before = (one('select count(*) from edu_session'), one('select count(*) from edu_tuition_payment'),
          one('select count(*) from edu_student'))
wiz2 = env['edu.import.wizard'].create({'file': data, 'filename': 'gvnn.xlsx', 'date_from': '2026-01-01'})
wiz2.action_import()
env.flush_all()
after = (one('select count(*) from edu_session'), one('select count(*) from edu_tuition_payment'),
         one('select count(*) from edu_student'))
print('RERUN before=%s after=%s idempotent=%s' % (before, after, before == after))
print('TOTAL_SECONDS', round(time.time() - t0, 1))

env.cr.rollback()
env['ir.sequence'].search([('code', 'in', ['edu.student', 'edu.tuition.payment', 'edu.tuition.refund'])]).write({'number_next_actual': 1})
env.cr.commit()
