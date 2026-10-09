# -*- coding: utf-8 -*-
from odoo import api, fields, models

RED = ('red_now', 'red')


class EduDashboard(models.AbstractModel):
    _name = 'edu.dashboard'
    _description = 'Dữ liệu trang chủ trung tâm GVNN'

    @api.model
    def get_data(self):
        user = self.env.user
        is_manager = user.has_group('edu_gvnn.group_edu_manager')
        Alert = self.env['edu.week.alert'].sudo()
        week = Alert._default_week()
        data = {
            'user_name': user.name,
            'is_manager': is_manager,
            'studying': self.env['edu.student'].search_count([('state', '=', 'studying')]),
            'stopped': self.env['edu.student'].search_count([('state', '=', 'stopped')]),
            'week': {'id': week.id, 'name': week.name} if week else False,
            'alerts': {},
            'priority_list': [],
            'finance': False,
        }
        if week:
            # Cảnh báo là ảnh chụp lúc tạo; tạo lại mỗi lần mở để số liệu luôn khớp học viên và buổi học.
            Alert._generate(week)
            base = [('week_id', '=', week.id)]
            count = lambda extra: Alert.search_count(base + extra)  # noqa
            data['alerts'] = {
                'absent': count([('absent', '=', True)]),
                'absent_3w': count([('absent_3w', '=', True)]),
                'fee_out': count([('fee_warning', '=', 'out')]),
                'fee_low': count([('fee_warning', '=', 'low')]),
                'red': count([('priority', 'in', RED)]),
                'suggest_stop': count([('suggest_stop', '=', True)]),
                'session_warnings': self.env['edu.session'].search_count([
                    ('week_id', '=', week.id), ('state', '=', 'done'), ('warning', '!=', 'ok')]),
            }
            data['priority_list'] = [{
                'id': a.id, 'student': a.student_id.name, 'priority': a.priority,
                'fee_warning': a.fee_warning, 'absent_streak': a.absent_streak,
                'action': a.action, 'balance': a.balance,
            } for a in Alert.search(base + [('priority', '!=', 'ok')], order='priority_order, student_id', limit=8)]
        if is_manager:
            data['finance'] = self._finance()
        return data

    def _finance(self):
        cr = self.env.cr
        self.env.flush_all()
        today = fields.Date.context_today(self)
        year_start = today.replace(month=1, day=1)
        cr.execute("""
            SELECT COALESCE(SUM(income), 0), COALESCE(SUM(salary), 0), COALESCE(SUM(other_expense), 0)
              FROM edu_report_finance WHERE date >= %s""", (year_start,))
        income, salary, expense = cr.fetchone()
        year, month = today.year, today.month - 11
        if month <= 0:
            year, month = year - 1, month + 12
        first = today.replace(year=year, month=month, day=1)
        cr.execute("""
            SELECT to_char(date_trunc('month', date), 'YYYY-MM') AS m,
                   SUM(income), SUM(salary + other_expense), SUM(cash_flow)
              FROM edu_report_finance WHERE date >= %s GROUP BY 1 ORDER BY 1""", (first,))
        rows = {m: (inc, cost, flow) for m, inc, cost, flow in cr.fetchall()}
        months = []
        for _ in range(12):
            key = '%04d-%02d' % (year, month)
            inc, cost, flow = rows.get(key, (0, 0, 0))
            months.append({'label': '%02d/%d' % (month, year), 'income': inc, 'cost': cost, 'flow': flow})
            month += 1
            if month > 12:
                year, month = year + 1, 1
        cr.execute("""
            SELECT EXTRACT(YEAR FROM date)::int AS y, SUM(income), SUM(salary + other_expense), SUM(cash_flow)
              FROM edu_report_finance GROUP BY 1 ORDER BY 1""")
        years = [{'label': str(y), 'income': inc, 'cost': cost, 'flow': flow}
                 for y, inc, cost, flow in cr.fetchall()]
        cr.execute("SELECT COALESCE(SUM(balance), 0) FROM edu_student WHERE state = 'studying' AND active")
        return {
            'year': today.year,
            'income': income, 'cost': salary + expense, 'salary': salary, 'other_expense': expense,
            'cash_flow': income - salary - expense, 'balance': cr.fetchone()[0],
            'months': months, 'years': years,
        }
