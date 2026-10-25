import secrets
import time

from odoo import http
from odoo.http import request
from odoo.exceptions import UserError


class GoogleVideoOAuth(http.Controller):
    def _error_response(self, message):
        return request.make_response(message, status=400, headers=[
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Cache-Control', 'no-store'),
            ('Referrer-Policy', 'no-referrer'),
        ])

    @http.route('/edu-video/google/callback', type='http', auth='user', methods=['GET'])
    def callback(self, state=None, code=None, error=None, **kwargs):
        pending = request.session.pop('edu_video_oauth', None)
        if (not request.env.user.has_group('base.group_system') or not pending
                or not isinstance(state, str)
                or not secrets.compare_digest(state, pending['state'])
                or pending['uid'] != request.env.uid
                or pending['db'] != request.env.cr.dbname
                or pending['expires'] < time.time()):
            return self._error_response('Phiên kết nối không hợp lệ hoặc đã hết hạn. Hãy kết nối lại từ Odoo.')
        if error == 'access_denied':
            return self._error_response(
                'Google đã từ chối cấp quyền (access_denied).\n\n'
                '1. Kiểm tra email đăng nhập đã có trong Google Auth Platform → Audience → Test users của đúng project.\n'
                '2. Quay lại Odoo, bấm Kết nối Google từ đầu và chọn đúng email đó.\n'
                '3. Với kết nối YouTube, chọn đúng kênh và cấp quyền YouTube. Với kết nối Drive, chọn tài khoản Google và cấp quyền đọc Drive. Sau đó bấm Tiếp tục/Cho phép.\n'
                'Nếu dùng tài khoản công ty/trường học và vẫn bị chặn, cần quản trị viên Google Workspace cho phép ứng dụng.\n\n'
                'Chưa có kết nối mới nào được lưu. Không cần tạo lại Client ID hoặc file JSON.')
        if error:
            return self._error_response('Google trả về lỗi khi cấp quyền. Hãy kết nối lại từ Odoo và kiểm tra cấu hình ứng dụng Google.')
        if not code:
            return self._error_response('Google không trả về mã xác thực. Hãy bấm Kết nối Google từ Odoo để bắt đầu lại.')
        config = request.env['edu.video.config'].browse(pending['config']).exists()
        if not config:
            return request.not_found()
        try:
            config._exchange(code, service=pending.get('service', 'youtube'), redirect_uri=pending.get('redirect_uri'))
        except UserError as exc:
            return self._error_response(str(exc))
        action = request.env.ref('edu_video.action_config').id
        response = request.redirect('/web#action=%s&id=%s&model=edu.video.config&view_type=form' % (action, config.id))
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        return response
