# -*- coding: utf-8 -*-
from odoo import fields, models


class EduWeekAlertWizard(models.TransientModel):
    _name = 'edu.week.alert.wizard'
    _description = 'Tạo cảnh báo tuần'

    week_id = fields.Many2one(
        'edu.week', 'Tuần', required=True,
        default=lambda self: self.env['edu.week.alert']._default_week())

    def action_generate(self):
        self.ensure_one()
        self.env['edu.week.alert'].sudo()._generate(self.week_id)
        return {
            'type': 'ir.actions.act_window', 'name': 'Cảnh báo %s' % self.week_id.name,
            'res_model': 'edu.week.alert', 'view_mode': 'tree,form',
            'domain': [('week_id', '=', self.week_id.id)],
            'context': {'search_default_not_ok': 1},
        }
