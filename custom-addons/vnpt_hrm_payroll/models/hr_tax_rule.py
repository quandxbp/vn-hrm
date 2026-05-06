from odoo import models, fields, api

class HrTaxRule(models.Model):
    _name = "hr.tax.rule"
    _description = "Quy tắc Thuế TNCN"

    name = fields.Char(string="Tên Quy tắc", required=True)
    tax_policy = fields.Selection([
        ('progressive', 'Biểu Thuế Lũy Tiến Từng Phần'),
        ('flat', 'Thuế Suất Cố Định')
    ], string="Chính sách thuế?", required=True, default="progressive")
    apply_deduction = fields.Boolean(string="Áp dụng Giảm trừ?", default=True)
    base_deduction = fields.Float(string="Giảm trừ Cơ sở tính Thuế thu nhập cá nhân", default=11000000)
    dependent_deduction = fields.Float(string="Giảm trừ cho mỗi người phụ thuộc", default=4400000)
    bracket_ids = fields.One2many("hr.tax.bracket", "tax_rule_id", string="Biểu Thuế Lũy Tiến Từng Phần")
    fixed_tax_rate = fields.Float(string="Thuế suất cố định", default=10)

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id
    )