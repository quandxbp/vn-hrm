from odoo import http
from odoo.http import request


class TeacherSessionReview(http.Controller):
    @http.route('/weekly-schedule/session-review', type='http', auth='public',
                methods=['POST'], csrf=True, sitemap=False)
    def session_review(self, edit_token=None, session_id=None, **kwargs):
        status, payload = request.env['edu.public.schedule']._teacher_session_review(edit_token, session_id)
        return request.make_json_response(payload, status=status, headers={
            'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
            'X-Content-Type-Options': 'nosniff', 'X-Robots-Tag': 'noindex, nofollow',
        })
