from odoo import api, fields, models

class ResWard(models.Model):
    _name = 'res.ward'
    _description = 'Ward'
    _order = 'name'
    _rec_names_search = ['name']

    name = fields.Char("Name", required=True, translate=True)
    country_id = fields.Many2one(comodel_name='res.country', string='Country', required=True)
    state_id = fields.Many2one(comodel_name='res.country.state', string='State', domain="[('country_id', '=', country_id)]")
    city_id = fields.Many2one(comodel_name='res.city', string='City', domain="[('state_id', '=', state_id)]")
    code = fields.Char("Code")
    division_type = fields.Char("Division Type")
    codename = fields.Char("Code")
