from odoo import api, models

from ..hooks import sync_landing_menus


class Website(models.Model):
    _inherit = 'website'

    @api.model
    def _sync_edu_landing_menus(self):
        sync_landing_menus(self.env)
