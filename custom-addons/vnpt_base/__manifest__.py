# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'VNPT: BASE',
    'version': '1.0',
    'summary': 'VNPT: Base',
    'description': """
VNPT Base Module
""",
    'website': ' ',
    'depends': ["base", "web"],

    'data': [
        'security/ir.model.access.csv',

        'views/templates.xml',
        'views/webclient_templates.xml',
        # 'views/auth_signup_login_templates.xml',

        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        
        'views/login/webclient_templates_right.xml',
        'views/login/webclient_templates_left.xml',
        'views/login/webclient_templates_middle.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'vnpt_base/static/src/scss/style.scss',

            'vnpt_base/static/src/js/*.js',
            'vnpt_base/static/src/user_menu/*.js',
        ],
        # 'web.assets_backend_prod_only': [
        #     'vnpt_base/static/src/main.js'
        # ],
    },

    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
