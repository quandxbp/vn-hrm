from odoo import models, fields, api

class HrContractAdvantageWizard(models.TransientModel):
    _name = "hr.contract.advantage.wizard"
    _description = "Wizard cập nhật phụ cấp hợp đồng"

    advantage_template_id = fields.Many2one(
        "hr.advantage.template",
        string="Đãi ngộ",
        required=True, readonly=True
    )
    amount = fields.Monetary(string="Tổng tiền", currency_field="currency_id")
    contract_ids = fields.Many2many("hr.contract", string="Hợp đồng", domain="[('state','=','open')]")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)

    def action_confirm(self):
        self.ensure_one()
        ContractAdvantage = self.env['hr.contract.advantage']

        for contract in self.contract_ids:
            # Kiểm tra xem hợp đồng này đã có phúc lợi này chưa
            existing = contract.advantage_ids.filtered(lambda a: a.advantage_template_id == self.advantage_template_id)
            # Tìm dòng cấu hình theo chức vụ nếu có
            matched_line = self.advantage_template_id.advantage_line_ids.filtered(lambda l: l.job_id == contract.job_id)
            final_amount = matched_line.amount if matched_line else self.amount

            if existing:
                # Nếu đã có thì cập nhật số tiền
                existing.amount = final_amount
                continue

            # Nếu chưa có thì tạo mới
            ContractAdvantage.create({
                'contract_id': contract.id,
                'advantage_template_id': self.advantage_template_id.id,
                'amount': final_amount,
            })



