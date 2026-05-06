# -*- coding:utf-8 -*-


from odoo import fields, models


class HrSalaryAttachment(models.Model):
    _name = 'hr.salary.attachment.type'
    _description = 'Salary Attachment Type'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    no_end_date = fields.Boolean()
    country_id = fields.Many2one('res.country')
