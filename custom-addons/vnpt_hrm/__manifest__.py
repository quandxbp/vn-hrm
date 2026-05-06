{
    'name': 'VNPT HRM Quản trị nguồn nhân lực',
    'version': '1.0',
    'summary': 'VNPT: HRM',
    'category': 'Hidden',
    'description': """
VNPT: HRM Customization
""",
    'website': ' ',
    'depends': ["vnpt_base", "hr", "hr_holidays", "hr_recruitment", "hr_contract",
                "hr_attendance", "hr_payroll"],

    'data': [
        "security/ir.model.access.csv",
        "security/hr_insurance_security.xml",

        "data/override_module_icon.xml",
        "data/hr_bank_data.xml",
        "data/hr_job_data.xml",
        "data/hr_employee_data.xml",
        "data/hr_employee_education_data.xml",
        "data/hr_employee_relatives_relationship_data.xml",
        "data/hr_ethnicity_religion_data.xml",

        "views/hr_employee_views.xml",
        "views/hr_employee_private_views.xml",
        "views/hr_employee_public_views.xml",
        "views/hr_insurance_views.xml",
        "views/hr_department_views.xml",
        "views/hr_ethnicity_religion_views.xml",

        # Modify other modules views
        "views/hr_holidays/hr_leave_views.xml",
        "views/hr_recruitment/hr_applicant_views.xml",
        "views/hr_recruitment/survey_invite_views.xml",

        "views/hr_contract/hr_contract_views.xml",

        "views/res_user_views.xml",
        "views/res_config_settings_views.xml",

        "views/replace_menuitems.xml",
        "views/menuitems.xml",
    ],
    'assets': {
        'web.assets_frontend': [
        ],
        'web.assets_backend': [
            'vnpt_hrm/static/src/scss/styles.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}
