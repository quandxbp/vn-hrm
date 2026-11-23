{
    'name': 'GVNN - Nhận xét AI chạy song song (worker nội bộ)',
    'version': '17.0.1.0.0',
    'license': 'LGPL-3',
    'summary': 'Gửi video đã có báo cáo Gemini sang review worker nội bộ để so sánh; không thay báo cáo chính.',
    'depends': ['edu_session_review'],
    'external_dependencies': {'python': ['requests']},
    'data': ['security/ir.model.access.csv', 'views/shadow.xml', 'data/cron.xml'],
    'installable': True,
}
