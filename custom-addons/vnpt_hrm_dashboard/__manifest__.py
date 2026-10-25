# -*- coding: utf-8 -*-
{
    'name' : 'Trung tâm GVNN: Trang chủ',
    'version' : '17.0.1.1.0',
    'summary': 'Dashboard trung tâm GVNN',
    'sequence': -1,
    'description': """Dashboard trung tâm GVNN""",
    'category': 'OWL',
    'depends' : ['edu_gvnn'],
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
        ],
    },
}
