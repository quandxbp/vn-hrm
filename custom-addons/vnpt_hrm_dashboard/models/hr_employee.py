from time import sleep

from odoo import api, fields, models
from lxml import etree
from datetime import date, timedelta, datetime


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)

        # Kiểm tra nếu người dùng đang xem chính mình
        employee = self.search([('user_id', '=', self.env.uid)], limit=1)
        if not employee:
            return res

        if view_type == 'form':
            doc = etree.XML(res['arch'])
            for field in doc.xpath("//field[@groups]"):
                field_name = field.get("name")
                # Chỉ xóa groups nếu field tồn tại trong model
                if field_name in self._fields:
                    field.attrib.pop('groups', None)
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    def action_open_employee_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Hồ sơ nhân sự',
            'res_model': 'hr.employee',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': self.env.context,
        }

    @api.model
    def action_open_current_employee_info(self, employee_id, employee_name):
        """Return action to open employee profile with a specific form view."""
        return {
            'type': 'ir.actions.act_window',
            'name': f"Hồ sơ - {employee_name}",
            'res_model': 'hr.employee.public',
            'res_id': employee_id,
            'views': [(self.env.ref('vnpt_hrm.vnpt_hr_employee_public_view_form').id, "form")],
            'target': 'current',
            'context': {
                'create': False,  # Disable creation
                'edit': False,  # Disable editing
                'delete': False,  # Disable deletion
            }
        }

    def get_current_employee_data(self, user_id):
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', user_id)], limit=1)
        return {
            "id": employee.id,
            "name": employee.name,
            "work_email": employee.work_email,
            "work_phone": employee.work_phone,
            "job_title": employee.job_title,
            "department_name": employee.department_name,
            "image_1920": employee.image_1920,
            "code": employee.code
        }

    def get_manager_alerts(self):
        company = self.env.user.company_id
        salary_warning_days = company.salary_increase_warning_left_days or 30
        contract_warning_days = company.expired_contract_warning_left_days or 30

        today = date.today()
        warning_contract_date = today + timedelta(days=contract_warning_days)
        warning_salary_date = today + timedelta(days=salary_warning_days)

        Contract = self.env['hr.contract'].sudo()

        nearly_expired_contracts = Contract.search([
            ('state', 'in', ['draft', 'open']),
            ('date_end', '<=', warning_contract_date),
            ('date_end', '>=', today)
        ])
        expired_contracts = Contract.search([
            ('state', '=', 'close'),
            ('date_end', '<=', today)
        ])
        salary_increase_contracts = Contract.search([
            ('state', 'in', ['draft', 'open']),
            ('next_salary_increment_date', '<=', warning_salary_date),
            ('next_salary_increment_date', '>=', today)
        ])

        return {
            "expiredContracts": expired_contracts.ids,
            "nearlyExpiredContracts": nearly_expired_contracts.ids,
            "salaryIncrease": salary_increase_contracts.ids,
            "counts": {
                "expiredContracts": len(expired_contracts),
                "nearlyExpiredContracts": len(nearly_expired_contracts),
                "salaryIncrease": len(salary_increase_contracts)
            }
        }

    def get_employee_birthdays(self):
        today = datetime.today()
        today_day = today.day
        today_month = today.month

        employees = self.env['hr.employee'].sudo().search([
            ('birthday', '!=', False),
            ('birthday', 'like', f"%-{today_month:02d}-{today_day:02d}")
        ])

        return [{
                'id': emp.id,
                'name': emp.name,
                'birthday': emp.birthday.strftime('%d/%m/%Y'),
                'job_title': emp.job_title,
                'work_email': emp.work_email,
            }
            for emp in employees
        ]
