from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HrAdvantageTemplate(models.Model):
    _name = "hr.advantage.template"
    _description = "Mẫu phụ cấp/đãi ngộ"

    name = fields.Char(string="Tên", required=True)
    code = fields.Char(string='Mã', required=True)

    amount = fields.Float(
        string="Số tiền hàng tháng",
        required=True,
        help="Phụ cấp mặc định hàng tháng", default=0.0

    )
    advantage_ids = fields.One2many('hr.contract.advantage', 'advantage_template_id', string='Phúc lợi/đãi ngộ')
    lower_limit = fields.Monetary(string='Giới hạn dưới', default=0.0)
    upper_limit = fields.Monetary(string='Giới hạn trên', default=0.0)

    description = fields.Char(string="Mô tả")

    amount_type = fields.Selection([
        ('monthly', 'Cơ sở hàng tháng'),
        ('yearly', 'Cơ sở hàng năm'),
        ('once', 'Một lần')
    ], string='Kiểu tổng', default='monthly')

    active = fields.Boolean(string="Active", default=True)
    advantage_line_ids = fields.One2many(
        "hr.advantage.line",
        "advantage_template_id",
        string="Thông tin phụ cấp"
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id
    )

    @api.onchange('amount')
    def _onchange_amount(self):
        if self.amount and self.upper_limit < self.amount:
            self.upper_limit = self.amount

    @api.constrains('advantage_line_ids')
    def _check_unique_job_id(self):
        for template in self:
            job_ids = template.advantage_line_ids.mapped('job_id.id')
            if len(job_ids) != len(set(job_ids)):
                raise ValidationError("Không thể chọn trùng chức vụ trong danh sách phụ cấp.")

    def action_update(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cập nhật phụ cấp hợp đồng',
            'res_model': 'hr.contract.advantage.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_advantage_template_id': self.id,
                'default_amount': self.amount,
            }
        }

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Mã phụ cấp phải là duy nhất!')
    ]

class HrAdvantageLine(models.Model):
    _name = 'hr.advantage.line'
    _description = 'Chi tiết phụ cấp theo chức vụ'

    job_id = fields.Many2one('hr.job', string='Chức vụ', required=True)
    advantage_template_id = fields.Many2one('hr.advantage.template', string='Mẫu phụ cấp', required=True, ondelete='cascade')
    code = fields.Char(string='Mã', related='advantage_template_id.code', store=True)
    amount = fields.Monetary(string='Số tiền hàng tháng')
    amount_type = fields.Selection([
        ('monthly', 'Cơ sở hàng tháng'),
        ('yearly', 'Cơ sở hàng năm'),
        ('once', 'Một lần')
    ], string='Kiểu tổng', default='monthly', related='advantage_template_id.amount_type', store=True)
    # computation_type = fields.Selection([
    #     ('fixed', 'Cố định'),
    #     ('percentage', 'Theo phần trăm'),
    #     ('formula', 'Theo công thức')
    # ], string='Kiểu nghĩ', default='fixed', required=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id.id)

    @api.constrains('amount', 'advantage_template_id')
    def _check_amount_range(self):
        for line in self:
            template = line.advantage_template_id
            if template and (line.amount < template.lower_limit or line.amount > template.upper_limit):
                raise ValidationError(
                    f"Số tiền '{line.amount}' phải nằm trong khoảng từ {template.lower_limit} đến {template.upper_limit}."
                )

class HrContractAdvantage(models.Model):
    _name = "hr.contract.advantage"
    _description = "Phúc lợi hợp đồng"

    contract_id = fields.Many2one("hr.contract", string="Hợp đồng", required=True, ondelete="cascade")
    employee_id = fields.Many2one("hr.employee", string="Nhân viên", related="contract_id.employee_id", store=True)
    job_id = fields.Many2one("hr.job", string="Chức vụ", related="contract_id.job_id", store=True)
    department_id = fields.Many2one("hr.department", string="Phòng ban", related="contract_id.department_id", store=True)
    advantage_template_id = fields.Many2one("hr.advantage.template", string="Đãi ngộ", required=True)
    name = fields.Char(related="advantage_template_id.name", string="Đãi ngộ", store=True)
    code = fields.Char(related="advantage_template_id.code", string="Mã", store=True)
    amount = fields.Monetary(string="Tổng tiền", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Tiền tệ", default=lambda self: self.env.company.currency_id)
