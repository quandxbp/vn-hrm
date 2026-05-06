from odoo import api, fields, models

class HrContract(models.Model):
    _inherit = "hr.contract"

    tax_rule_id = fields.Many2one('hr.tax.rule', string="Quy tắc thuế")
    grade_id = fields.Many2one('hr.job.grade', string="Bậc lương", domain="[('job_id', '=', job_id)]")
    salary_coefficient = fields.Float(string="Hệ số lương", related="grade_id.salary_coefficient", store=True)
    insurance_wage = fields.Monetary(string="Lương đóng BH", related="grade_id.insurance_wage", store=True)

    @api.onchange("job_id")
    def _onchange_job_id(self):
        self.grade_id = False

    def sync_wage_from_grade(self):
        for contract in self:
            if contract.grade_id:
                contract.wage = contract.grade_id.base_wage
            else:
                contract.wage = 0.0