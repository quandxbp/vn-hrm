from odoo import api, models

from ..hooks import sync_landing_menus


class Website(models.Model):
    _inherit = 'website'

    @api.model
    def _sync_edu_landing_menus(self):
        sync_landing_menus(self.env)

    def _get_landing_activities(self):
        self.ensure_one()
        return self.env['edu.landing.activity'].search([
            ('is_published', '=', True),
            ('event_id.active', '=', True),
            '|', ('website_id', '=', False), ('website_id', '=', self.id),
        ])

    def _get_landing_students(self):
        self.ensure_one()
        return self.env['edu.landing.student'].search([
            ('is_published', '=', True),
            '|', ('website_id', '=', False), ('website_id', '=', self.id),
        ])

    def _get_landing_teachers(self):
        self.ensure_one()
        return self.env['edu.landing.teacher'].search([
            ('is_published', '=', True),
            '|', ('website_id', '=', False), ('website_id', '=', self.id),
        ])
