from odoo import api, fields, models

class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    # code = fields.Char(related='employee_id.code')
    gender = fields.Selection(related='employee_id.gender')
    birthday = fields.Date(related='employee_id.birthday')
    marital = fields.Selection(related='employee_id.marital')
    private_street = fields.Char(related='employee_id.private_street')
    private_street2 = fields.Char(related='employee_id.private_street2')
    private_zip = fields.Char(related='employee_id.private_zip')
    private_city = fields.Char(related='employee_id.private_city')
    private_state_id = fields.Many2one(related='employee_id.private_state_id')
    private_country_id = fields.Many2one(related='employee_id.private_country_id')
    private_email = fields.Char(related='employee_id.private_email')
    so_bhxh = fields.Char(related='employee_id.so_bhxh')

    identification_id = fields.Char(related='employee_id.identification_id')
    passport_id = fields.Char(related='employee_id.passport_id')
    place_of_birth = fields.Char(related='employee_id.place_of_birth')
    country_id = fields.Many2one(related='employee_id.country_id')

    certificate = fields.Selection(related='employee_id.certificate')
    study_field = fields.Char(related='employee_id.study_field')
    study_school = fields.Char(related='employee_id.study_school')
    # full_address = fields.Char(related='employee_id.full_address')

