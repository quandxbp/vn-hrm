from odoo import models, fields, api

class HrTaxBracket(models.Model):
    _name = "hr.tax.bracket"
    _description = "Bậc thuế thu nhập cá nhân"

    tax_rule_id = fields.Many2one("hr.tax.rule", string="Quy tắc Thuế", ondelete="cascade", required=True)
    lower_limit = fields.Float(string="Cơ sở tính thuế", required=True)
    tax_rate = fields.Float(string="Tỷ lệ (%)", required=True)