# -*- coding: utf-8 -*-
{
    'name' : 'VNPT HRM: Bảng lương',
    'version' : '1.0',
    'summary': 'VNPT HRM Payroll',
    'sequence': -1,
    'description': """VNPT HRM Payroll""",
    'category': 'OWL',
    'depends' : ['hr_payroll'],
    'data': [
        'data/hr_payroll_data.xml',
        'data/hr_tax_rule_data.xml',
        "security/ir.model.access.csv",

        'views/hr_payslip_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_tax_rule_views.xml',
        'views/hr_tax_bracket_views.xml',
        "views/hr_job_grade_views.xml",
        'views/menuitems.xml',
    ],
    'demo': [

    ],
    'installable': True,
    'application': False,
    'assets': {
        'web.assets_backend': [

        ],
    },
}
