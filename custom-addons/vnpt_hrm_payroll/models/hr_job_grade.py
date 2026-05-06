from odoo import models, fields, api

class HrJobGrade(models.Model):
    _name = 'hr.job.grade'
    _description = 'Job Salary Grade'
    _order = 'job_id, grade_level desc'

    job_id = fields.Many2one('hr.job', string="Chức vụ", required=True, ondelete='cascade')
    category_id = fields.Many2one('hr.job.grade.category', string="Nhóm bậc lương", required=True)
    grade_level = fields.Integer(string="Bậc lương", required=True)
    salary_coefficient = fields.Float(string="Hệ số lương", required=True)
    base_wage = fields.Monetary(string="Mức lương cơ bản", required=True)
    insurance_wage = fields.Monetary(string="Lương cơ bản đóng BH", required=True)
    currency_id = fields.Many2one('res.currency', string="Currency", required=True, default=lambda self: self.env.company.currency_id)

    @api.depends("job_id", "grade_level")
    def _compute_display_name(self):
        super()._compute_display_name()
        for rec in self:
            if rec.category_id and rec.grade_level:
                rec.display_name = f"Bậc {rec.grade_level} - {rec.category_id.name}"
            elif rec.grade_level:
                rec.display_name = f"Bậc {rec.grade_level}"
            else:
                rec.display_name = "Bậc lương mới"