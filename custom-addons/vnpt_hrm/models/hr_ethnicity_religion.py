from odoo import api, fields, models

class HrEthnicity(models.Model):
    _name = 'hr.ethnicity'

    code = fields.Char(string="Mã")
    name = fields.Char(string="Tên", required=True)
    note = fields.Text(string="Ghi chú")
    active = fields.Boolean(string="Kích hoạt", default=True)

class HrReligion(models.Model):
    _name = 'hr.religion'

    code = fields.Char(string="Mã")
    name = fields.Char(string="Tên", required=True)
    note = fields.Text(string="Ghi chú")
    active = fields.Boolean(string="Kích hoạt", default=True)
