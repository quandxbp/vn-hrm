{
    'name': 'GVNN - Nhận xét AI chạy song song (worker nội bộ)',
    'version': '17.0.1.4.0',
    'license': 'LGPL-3',
    'summary': 'Kim Worker (review worker nội bộ): báo cáo AI chính cho buổi chưa có nhận xét, Gemini dự phòng; so sánh với Gemini.',
    'depends': ['edu_session_review'],
    'external_dependencies': {'python': ['requests']},
    'data': ['security/ir.model.access.csv', 'views/shadow.xml', 'views/session.xml', 'views/highlight.xml', 'data/cron.xml'],
    'installable': True,
}
