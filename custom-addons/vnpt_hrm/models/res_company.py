# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    salary_increase_warning_left_days = fields.Integer(default=30)
    expired_contract_warning_left_days = fields.Integer(default=30)
