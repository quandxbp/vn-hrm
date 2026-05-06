from odoo import models, fields, api

class HrJobGradeCategory(models.Model):
    _name = 'hr.job.grade.category'
    _description = 'Loại bậc lương'


    name = fields.Char(string="Tên nhóm", required=True)
    code = fields.Char(string="Mã nhóm", required=True)