from odoo import api, fields, models

class HrContract(models.Model):
    _inherit = "hr.contract"

    next_salary_increment_date = fields.Date(string="Ngày nâng lương tiếp theo")
    job_title = fields.Char(related="employee_id.job_title", string="Chức vụ")

    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Thêm tài liệu",
        tracking=True
    )