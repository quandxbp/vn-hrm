# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    salary_increase_warning_left_days = fields.Integer(related="company_id.salary_increase_warning_left_days", readonly=False)
    expired_contract_warning_left_days = fields.Integer(related="company_id.expired_contract_warning_left_days", readonly=False)
    employee_code_prefix = fields.Char(string="Ký tự đầu mã nhân viên", config_parameter="vnpt_hrm.employee_code_prefix",
                                       default="BPC")

