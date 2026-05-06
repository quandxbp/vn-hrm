from odoo import models, fields, api

class HrPayslipIncomeTax(models.Model):
    _name = "hr.payslip.income.tax"
    _description = "Thuế luỹ tiến từng phần"

    slip_id = fields.Many2one('hr.payslip', string="Phiếu lương", ondelete="cascade")
    personal_tax_base = fields.Monetary(string="Thu nhập bị tính thuế")
    upper_base = fields.Monetary(string="Cơ sở tính thuế")
    personal_tax_rate = fields.Float(string="Tỷ lệ (%)")
    tax_amount = fields.Monetary(string="Giá trị thuế")
    description = fields.Char(string="Mô tả")
    currency_id = fields.Many2one('res.currency', string="Tiền tệ", related="slip_id.currency_id", readonly=True)


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    personal_tax_rule_id = fields.Many2one("hr.tax.rule", related='contract_id.tax_rule_id', store=True, readonly=True)
    personal_tax_apply_deduction = fields.Boolean(related='personal_tax_rule_id.apply_deduction', store=True)
    personal_tax_policy = fields.Selection(related="personal_tax_rule_id.tax_policy", string="Chính sách thuế thu nhập cá nhân",
                                  store=True, readonly=True)
    personal_fixed_tax_rate = fields.Float(related='personal_tax_rule_id.fixed_tax_rate', store=True, readonly=True)
    personal_tax_base_deduction = fields.Float(string="Giảm trừ bản thân",
                                               related='personal_tax_rule_id.base_deduction', store=True, readonly=True)
    personal_total_dependant = fields.Integer(string="Số người phụ thuộc",
                                                        related="employee_id.total_dependant", store=True)
    personal_dependent_deduction = fields.Float(string="Giảm trừ cho mỗi người phụ thuộc",
                                                related='personal_tax_rule_id.dependent_deduction')
    total_dependent_deduction = fields.Float(string="Giảm trừ người phụ thuộc", compute='_compute_total_dependent_deduction',
                                             store=True)
    personal_tax_base = fields.Monetary(
        string="Cơ sở tính thuế TNCN",
        compute="_compute_basic_tax",
        store=True
    )
    tbded_wage = fields.Monetary(
        string="Giảm trừ cơ sở tính thuế",
        compute="_compute_basic_tax",
        store=True
    )
    ptax_wage = fields.Monetary(
        string="Thuế TNCN",
        compute="_compute_basic_tax",
        store=True
    )
    payslip_personal_income_tax_ids = fields.One2many(
        'hr.payslip.income.tax', 'slip_id',
        compute="_compute_basic_tax",
        store=True
    )

    @api.depends('line_ids.total')
    def _compute_basic_tax(self):
        line_values = self._origin._get_line_values(['TBDED', 'TAXBASE', 'PTAX'])
        for payslip in self:
            payslip.personal_tax_base = line_values['TAXBASE'][payslip._origin.id]['total']
            payslip.tbded_wage = line_values['TBDED'][payslip._origin.id]['total']
            payslip.ptax_wage = line_values['PTAX'][payslip._origin.id]['total']

            # Tính toán bảng thuế lũy tiến từng phần
            tax_lines = []
            payslip.payslip_personal_income_tax_ids.unlink()
            tax_brackets = payslip.personal_tax_rule_id.bracket_ids.sorted('tax_rate', reverse=True)
            tax_base = payslip.personal_tax_base

            for rule in tax_brackets:
                if tax_base > rule.lower_limit:
                    diff = tax_base - rule.lower_limit
                    tax_lines.append((0, 0, {
                        'slip_id': payslip.id,
                        'personal_tax_base': tax_base,
                        'upper_base': diff,
                        'description': f"Lớn hơn {rule.lower_limit:,.0f} ₫".replace(",", "."),
                        'personal_tax_rate': rule.tax_rate,
                        'tax_amount': rule.tax_rate * diff / 100.0,
                    }))
                    tax_base -= diff

            payslip.payslip_personal_income_tax_ids = tax_lines

    @api.depends("personal_total_dependant", "personal_dependent_deduction")
    def _compute_total_dependent_deduction(self):
        for rec in self:
            rec.total_dependent_deduction = (rec.personal_total_dependant or 0) * (rec.personal_dependent_deduction or 0)