from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrSalaryRuleCategory(models.Model):
    _name = 'hr.salary.rule.category'
    _description = 'Salary Rule Category'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    parent_id = fields.Many2one('hr.salary.rule.category', string='Parent',
        help="Linking a salary category to its parent is used only for the reporting purpose.")
    children_ids = fields.One2many('hr.salary.rule.category', 'parent_id', string='Children')
    note = fields.Html(string='Description')
    paid_by_company = fields.Boolean(string="Thanh toán bởi công ty?")
    salary_rule_ids = fields.One2many('hr.salary.rule', 'category_id', string='Salary Rules')
    salary_rules_count = fields.Integer(compute='_compute_salary_rules_count', string='Salary Rules Count')

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('Error! You cannot create recursive hierarchy of Salary Rule Category.'))

    def _sum_salary_rule_category(self, localdict, amount):
        self.ensure_one()
        if self.parent_id:
            localdict = self.parent_id._sum_salary_rule_category(localdict, amount)
        localdict['categories'][self.code] = localdict['categories'][self.code] + amount
        return localdict

    def _compute_salary_rules_count(self):
        for category in self:
            category.salary_rules_count = len(category.salary_rule_ids)

    def action_view_salary_rules(self):
        self.ensure_one()
        action = self.env.ref('hr_payroll.action_salary_rule_form').read()[0]
        action['domain'] = [('category_id', '=', self.id)]
        return action
