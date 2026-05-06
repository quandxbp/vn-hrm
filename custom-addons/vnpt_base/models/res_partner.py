from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _default_country(self):
        return self.env['res.country'].search([('code', '=', 'VN')], limit=1)

    def _default_state(self):
        return self.env['res.country.state'].search([('code', '=', 'VN-58')], limit=1)

    ward_id = fields.Many2one('res.ward', string='Ward', domain="[('city_id', '=', city_id)]")
    city_id = fields.Many2one('res.city', string='City', domain="[('state_id', '=', state_id)]")
    city = fields.Char(compute='_compute_city', store=True)
    full_address = fields.Char(string='Full Address', compute="_compute_full_address", store=True)
    country_id = fields.Many2one('res.country', default=_default_country)
    state_id = fields.Many2one('res.country.state', default=_default_state)

    @api.depends('city_id')
    def _compute_city(self):
        self.city = self.city_id.name

    @api.depends("ward_id", "city_id", "country_id", "state_id")
    def _compute_full_address(self):
        for rec in self:
            address_lst = [x for x in [rec.state_id.name, rec.country_id.name, rec.city_id.name, rec.ward_id.name] if x]
            rec.full_address = ", ".join(address_lst)


