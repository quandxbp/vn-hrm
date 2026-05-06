

from odoo import api, fields, models
from collections import defaultdict


class ContractHistory(models.Model):
    _inherit = 'hr.contract.history'

    time_credit = fields.Boolean('Credit time', readonly=True, help='This is a credit time contract.')
    work_time_rate = fields.Float(string='Work time rate', help='Work time rate versus full time working schedule.')
    standard_calendar_id = fields.Many2one('resource.calendar', readonly=True)
