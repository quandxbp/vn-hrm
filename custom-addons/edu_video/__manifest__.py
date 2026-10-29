{
    'name': 'GVNN - Google Video',
    'version': '17.0.1.8.0',
    'license': 'LGPL-3',
    'depends': ['edu_gvnn'],
    'external_dependencies': {'python': ['requests', 'PIL']},
    'data': ['security/ir.model.access.csv', 'views/config.xml', 'views/video.xml', 'data/cron.xml'],
    'installable': True,
}
