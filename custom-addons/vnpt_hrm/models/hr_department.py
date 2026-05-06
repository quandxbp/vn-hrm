from odoo import api, fields, models

class HrDepartment(models.Model):
    _inherit = "hr.department"

    code = fields.Char(string="Mã phòng ban")
