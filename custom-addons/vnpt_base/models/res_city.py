from odoo import api, fields, models

class ResCity(models.Model):
    _name = 'res.city'
    _description = 'City'
    _order = 'name'
    _rec_names_search = ['name', 'zipcode']

    name = fields.Char("Name", required=True, translate=True)
    code = fields.Char("Code")
    division_type = fields.Char("Division Type")
    codename = fields.Char("Code")
    country_id = fields.Many2one(comodel_name='res.country', string='Country', required=True)
    state_id = fields.Many2one(comodel_name='res.country.state', string='State', domain="[('country_id', '=', country_id)]")

    @api.depends('code')
    def _compute_display_name(self):
        for city in self:
            name = city.name if not city.code else f'{city.name} ({city.code})'
            city.display_name = name
