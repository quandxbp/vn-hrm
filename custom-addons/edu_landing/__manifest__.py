# -*- coding: utf-8 -*-
{
    'name': 'Landing page: Trung tâm Anh ngữ',
    'version': '17.0.1.0.0',
    'summary': 'Trang giới thiệu trung tâm tiếng Anh, form đăng ký tư vấn đổ vào CRM',
    'description': """
Trang chủ cho trung tâm tiếng Anh dựng trên Odoo Website (bản Community).
Các khối nằm trong vùng oe_structure nên vẫn sửa được bằng trình dựng kéo thả.
Form đăng ký tạo lead trong CRM.
""",
    'category': 'Website',
    'depends': ['website', 'website_crm'],
    'data': [
        'views/assets.xml',
        'views/homepage.xml',
        'views/footer.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'assets': {
        'web.assets_frontend': [
            'edu_landing/static/src/scss/landing.scss',
            'edu_landing/static/src/js/landing.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
