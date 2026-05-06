from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = "res.users"

    action_id = fields.Many2one(
        'ir.actions.actions',
        string="Home Action",
        default=lambda self: self._default_home_action()
    )

    @api.model
    def _default_home_action(self):
        """Set default home action for new users"""
        return self.env.ref('vnpt_hrm_dashboard.action_owl_hrm_dashboard').id