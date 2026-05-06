{
    'name': 'Customize Login Page Style',
    'version': '17.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Customize The Login Page With Different Styles',
    'description': 'The Module helps to customize login page with different '
                   'styles',
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['base','base_setup','web'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/webclient_templates_right.xml',
        'views/webclient_templates_left.xml',
        'views/webclient_templates_middle.xml',
    ],
    'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
