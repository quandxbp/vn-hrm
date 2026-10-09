# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class EduReportFinance(models.Model):
    """Thu, doanh thu ghi nhận, lương GV và chi phí khác gộp theo ngày, để làm báo cáo tài chính."""
    _name = 'edu.report.finance'
    _description = 'Báo cáo tài chính'
    _auto = False
    _order = 'date desc'

    date = fields.Date('Ngày', readonly=True)
    source = fields.Selection(
        [('income', 'Thu học phí'), ('revenue', 'Doanh thu ghi nhận'),
         ('salary', 'Lương GV'), ('expense', 'Chi phí khác')], string='Nguồn', readonly=True)
    income = fields.Float('Tiền thu học phí', digits=(16, 2), readonly=True)
    revenue = fields.Float('Doanh thu ghi nhận (tiền đã học)', digits=(16, 2), readonly=True)
    salary = fields.Float('Lương GV', digits=(16, 2), readonly=True)
    other_expense = fields.Float('Chi phí khác', digits=(16, 2), readonly=True)
    total_cost = fields.Float('Tổng chi phí', digits=(16, 2), readonly=True)
    cash_flow = fields.Float('Dòng tiền sau chi', digits=(16, 2), readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW edu_report_finance AS (
                SELECT row_number() OVER () AS id, src.source, src.date, src.income, src.revenue,
                       src.salary, src.other_expense,
                       src.salary + src.other_expense AS total_cost,
                       src.income - src.salary - src.other_expense AS cash_flow
                FROM (
                    SELECT 'income' AS source, p.date, p.amount AS income, 0.0 AS revenue,
                           0.0 AS salary, 0.0 AS other_expense
                      FROM edu_tuition_payment p
                    UNION ALL
                    SELECT 'revenue', a.date, 0.0, a.charge_amount, 0.0, 0.0
                      FROM edu_session_attendee a WHERE a.charge_amount <> 0
                    UNION ALL
                    SELECT 'salary', s.date, 0.0, 0.0, s.teacher_amount, 0.0
                      FROM edu_session s WHERE s.teacher_amount <> 0
                    UNION ALL
                    SELECT 'expense', e.date, 0.0, 0.0, 0.0, e.amount
                      FROM edu_other_expense e
                ) src
            )""")
