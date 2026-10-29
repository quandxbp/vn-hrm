{
    'name': 'GVNN - Nhận xét AI buổi học',
    'version': '17.0.2.1.0',
    'license': 'LGPL-3',
    'depends': ['edu_video'],
    'external_dependencies': {'python': ['requests']},
    'data': ['security/ir.model.access.csv', 'views/review.xml', 'data/cron.xml'],
    'assets': {'web.assets_backend': ['edu_session_review/static/src/scss/review.scss']},
    'installable': True,
}
