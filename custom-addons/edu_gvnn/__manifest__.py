# -*- coding: utf-8 -*-
{
    'name': 'Trung tâm GVNN: Điểm danh, học phí, lương giáo viên',
    'version': '17.0.1.0.0',
    'summary': 'Quản lý lớp luyện nói online với giáo viên nước ngoài',
    'description': """
Thay cho file TỔNG HỢP_GVNN.xlsx: giáo viên và đơn giá, lớp, học viên, buổi học,
thu học phí, kỳ lương, đối soát Agency, cảnh báo tuần và báo cáo tài chính.
Kế hoạch chi tiết: docs/GVNN_PLAN.md
""",
    'category': 'Education',
    'depends': ['base', 'mail', 'web', 'vnpt_base'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/config_data.xml',
        'data/sequence_data.xml',
        'data/expense_category_data.xml',
        'views/teacher_views.xml',
        'views/class_views.xml',
        'views/student_views.xml',
        'views/alert_report_views.xml',
        'views/session_views.xml',
        'report/tuition_receipt_report.xml',
        'report/payroll_report.xml',
        'views/tuition_payment_views.xml',
        'views/payroll_views.xml',
        'views/week_views.xml',
        'views/expense_category_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'views/import_views.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
