# -*- coding: utf-8 -*-
{
    'name' : 'VNPT HRM: Trang chủ',
    'version' : '1.0',
    'summary': 'VNPT HRM Dashboard',
    'sequence': -1,
    'description': """VNPT HRM Dashboard""",
    'category': 'OWL',
    'depends' : ['vnpt_hrm'],
    'data': [
        'views/menuitems.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'vnpt_hrm_dashboard/static/src/components/**/*.js',
            'vnpt_hrm_dashboard/static/src/components/**/*.xml',
            'vnpt_hrm_dashboard/static/src/components/**/*.scss',
            'vnpt_hrm_dashboard/static/src/scss/*.css',
        ],
    },
}
