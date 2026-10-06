from time import sleep

from odoo import api, fields, models
from lxml import etree
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta


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

    @api.model
    def get_dashboard_stats(self):
        """Số liệu tổng quan cho dashboard. Chỉ trả về cho quản lý nhân sự."""
        if not self.env.user.has_group('hr.group_hr_user'):
            return {}

        Employee = self.env['hr.employee'].sudo()
        Contract = self.env['hr.contract'].sudo()
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)

        def hired_between(start, end):
            # Ưu tiên "Ngày vào đơn vị", nếu trống thì lấy ngày tạo hồ sơ.
            return [
                '|',
                '&', ('ngay_vao_don_vi', '>=', start), ('ngay_vao_don_vi', '<', end),
                '&', ('ngay_vao_don_vi', '=', False),
                '&', ('create_date', '>=', start), ('create_date', '<', end),
            ]

        hires_by_month = []
        for offset in range(5, -1, -1):
            start = month_start - relativedelta(months=offset)
            end = start + relativedelta(months=1)
            hires_by_month.append({
                'label': start.strftime('%m/%Y'),
                'count': Employee.search_count(hired_between(start, end)),
            })

        departments = Employee._read_group([], ['department_id'], ['__count'])
        by_department = sorted(
            ({'label': dept.name or 'Chưa phân bổ', 'count': count} for dept, count in departments),
            key=lambda item: item['count'], reverse=True,
        )[:8]

        state_labels = dict(Contract._fields['state']._description_selection(self.env))
        contract_groups = Contract._read_group(
            [('state', 'in', ['draft', 'open', 'close'])], ['state'], ['__count'])
        contracts_by_state = [
            {'key': state, 'label': state_labels.get(state, state), 'count': count}
            for state, count in contract_groups
        ]

        now = fields.Datetime.now()
        on_leave_today = self.env['hr.leave'].sudo().search_count([
            ('state', '=', 'validate'),
            ('date_from', '<=', now),
            ('date_to', '>=', now),
        ])

        return {
            'total': Employee.search_count([]),
            'newThisMonth': hires_by_month[-1]['count'],
            'onLeaveToday': on_leave_today,
            'hiresByMonth': hires_by_month,
            'byDepartment': by_department,
            'contractsByState': contracts_by_state,
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
