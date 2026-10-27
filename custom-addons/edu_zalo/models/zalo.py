import hashlib
import uuid
from datetime import datetime

import pytz
import requests

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

TZ = pytz.timezone('Asia/Ho_Chi_Minh')


def split_message(text, limit=1800):
    parts = []
    while len(text) > limit:
        end = text.rfind('\n\n', 0, limit)
        if end < 1:
            end = text.rfind('\n', 0, limit)
        if end < 1:
            end = limit
        parts.append(text[:end])
        text = text[end:].lstrip('\n')
    if text:
        parts.append(text)
    return parts


class ZaloGroup(models.Model):
    _name = 'edu.zalo.group'
    _description = 'Nhóm Zalo'
    _order = 'name'

    name = fields.Char(required=True)
    zalo_id = fields.Char(required=True, index=True)
    _sql_constraints = [('zalo_id_unique', 'unique(zalo_id)', 'Nhóm Zalo đã tồn tại.')]


class ZaloConfig(models.Model):
    _name = 'edu.zalo.config'
    _description = 'Gửi lịch học Zalo'

    name = fields.Char(default='Lịch học Zalo', required=True)
    state = fields.Selection([('disconnected', 'Chưa đăng nhập'), ('connecting', 'Đang tạo QR'),
        ('qr', 'Chờ quét QR'), ('scanned', 'Chờ xác nhận trên điện thoại'), ('connected', 'Đã kết nối')],
        default='disconnected', readonly=True)
    qr = fields.Binary('Mã QR đăng nhập', readonly=True, attachment=False)
    account = fields.Char('Tài khoản Zalo', readonly=True)
    preferred_group = fields.Char('Tên nhóm cần tìm',
        help='Nhập tên, bấm Chọn nhóm theo tên, rồi Xác nhận nhóm nhận để đổi nhóm gửi mặc định.')
    group_id = fields.Many2one('edu.zalo.group', 'Nhóm nhận lịch', ondelete='restrict')
    confirmed_group_id = fields.Many2one('edu.zalo.group', 'Nhóm đã xác nhận', readonly=True, ondelete='restrict')
    auto_send = fields.Boolean('Tự động gửi hằng ngày', default=False,
        help='Theo giờ Việt Nam. Gửi trong vòng 30 phút kể từ giờ đã chọn khi máy chủ hoạt động.')
    send_hour = fields.Float('Giờ gửi (giờ Việt Nam)', required=True, default=9.0,
        help='Ví dụ 09:00. Máy chủ cần hoạt động trong vòng 30 phút kể từ giờ gửi.')
    preview_date = fields.Date('Ngày gửi lịch', default=lambda self: datetime.now(TZ).date(), required=True)
    preview = fields.Text('Nội dung lịch', compute='_compute_preview')
    log_ids = fields.One2many('edu.zalo.message', 'config_id', 'Lịch sử gửi')

    @api.model
    def _manager(self):
        if not self.env.su and not self.env.user.has_group('edu_gvnn.group_edu_manager'):
            raise AccessError('Chỉ Quản lý được sử dụng kết nối Zalo.')

    @api.model
    def _bridge(self, method, endpoint, payload=None):
        self._manager()
        params = self.env['ir.config_parameter'].sudo()
        url = params.get_param('edu_zalo.bridge_url', 'http://zalo-bridge:3000').rstrip('/')
        token = params.get_param('edu_zalo.bridge_token')
        if not token:
            raise UserError('Chưa cấu hình khóa kết nối Zalo trên máy chủ.')
        try:
            response = requests.request(method, url + endpoint, json=payload,
                headers={'Authorization': 'Bearer ' + token}, timeout=(5, 45))
            result = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise UserError('Cầu nối Zalo chưa phản hồi. Hãy kiểm tra kết nối rồi thử lại.') from exc
        if response.status_code >= 400:
            raise UserError(result.get('error', 'Kết nối Zalo thất bại.'))
        return result

    def action_login(self):
        self.ensure_one()
        self._bridge('POST', '/login', {})
        return self.action_refresh()

    def action_disconnect(self):
        self.ensure_one()
        self._bridge('POST', '/disconnect', {})
        self.write({'auto_send': False, 'confirmed_group_id': False, 'state': 'disconnected',
            'qr': False, 'account': False})
        return self._reopen()

    def action_refresh(self):
        self.ensure_one()
        status = self._bridge('GET', '/status')
        self.write({'state': status['state'], 'qr': status.get('qr') or False,
            'account': status.get('account') or False})
        if self.state == 'connected':
            self._refresh_groups()
        return self._reopen()

    def _refresh_groups(self):
        self.ensure_one()
        groups = self._bridge('GET', '/groups')['groups']
        Group = self.env['edu.zalo.group'].sudo()
        for item in groups:
            group = Group.search([('zalo_id', '=', item['id'])], limit=1)
            if group:
                group.name = item['name']
            else:
                Group.create({'name': item['name'], 'zalo_id': item['id']})
        if not self.group_id and self.preferred_group:
            matches = Group.search([('name', '=', self.preferred_group), ('zalo_id', 'in', [g['id'] for g in groups])])
            if len(matches) == 1:
                self.group_id = matches

    def action_confirm_group(self):
        self.ensure_one()
        if not self.group_id:
            raise UserError('Hãy chọn nhóm nhận lịch.')
        self._bridge('POST', '/target', {'group_id': self.group_id.zalo_id})
        self.confirmed_group_id = self.group_id
        return self._reopen()

    def action_select_preferred_group(self):
        self.ensure_one()
        self._manager()
        wanted = ' '.join((self.preferred_group or '').split()).casefold()
        if not wanted:
            raise UserError('Hãy nhập tên nhóm cần tìm.')
        groups = self._bridge('GET', '/groups')['groups']
        matches = [g for g in groups if ' '.join(g['name'].split()).casefold() == wanted]
        if len(matches) != 1:
            raise UserError('Không tìm thấy một nhóm duy nhất có tên này. Hãy kiểm tra tên nhóm và tài khoản Zalo.')
        match = matches[0]
        Group = self.env['edu.zalo.group'].sudo()
        group = Group.search([('zalo_id', '=', match['id'])], limit=1)
        if group:
            group.name = match['name']
        else:
            group = Group.create({'name': match['name'], 'zalo_id': match['id']})
        values = {'group_id': group.id}
        if group != self.confirmed_group_id:
            values['auto_send'] = False
        self.write(values)
        return self._reopen()

    @api.constrains('send_hour')
    def _check_send_hour(self):
        for config in self:
            if not 0 <= config.send_hour < 24:
                raise ValidationError('Giờ gửi phải từ 00:00 đến trước 24:00.')

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'current'}

    @api.constrains('auto_send', 'group_id', 'confirmed_group_id')
    def _check_target(self):
        for record in self:
            if record.auto_send and (not record.group_id or record.group_id != record.confirmed_group_id):
                raise UserError('Cần xác nhận đúng nhóm nhận trước khi bật gửi tự động.')

    @api.depends('preview_date')
    def _compute_preview(self):
        for record in self:
            record.preview = record._schedule_text(record.preview_date) if record.preview_date else ''

    @api.model
    def _schedule_text(self, day):
        sessions = self.env['edu.session'].search([('date', '=', day), ('state', '!=', 'cancel')], order='time_start, teacher_id, id')
        if not sessions:
            return 'Không có lịch học ngày %s.' % day.strftime('%d/%m/%Y')
        def hour(value):
            minutes = round(value * 60) % 1440
            return '%02d:%02d' % divmod(minutes, 60)
        blocks = ['LỊCH HỌC GVNN — %s' % day.strftime('%d/%m/%Y')]
        groups = {}
        for session in sessions:
            attendees = session.attendee_ids.filtered('present').mapped('student_id.name')
            students = ', '.join(attendees) or session.extra_participants or 'Chưa có học viên'
            if session.session_type == 'testing':
                students = 'Buổi testing'
            teacher = session.teacher_id
            if teacher.id not in groups:
                groups[teacher.id] = (teacher, [])
            groups[teacher.id][1].append('%s–%s: %s' % (
                hour(session.time_start), hour(session.time_end), students.upper()))
        for teacher, lessons in groups.values():
            blocks.append('%s\n%s\nLINK HỌC: %s' % (
                teacher._schedule_label(), '\n'.join(lessons),
                teacher.meeting_url or 'CHƯA CẤU HÌNH LINK HỌC'))
        return '\n\n'.join(blocks)

    def _queue(self, day, manual=False):
        self.ensure_one()
        if not self.group_id or self.group_id != self.confirmed_group_id:
            raise UserError('Hãy chọn và xác nhận nhóm nhận lịch trước.')
        Message = self.env['edu.zalo.message'].sudo()
        self.env.cr.execute('SELECT id FROM edu_zalo_config WHERE id = %s FOR UPDATE', [self.id])
        domain = [('date', '=', day), ('group_zalo_id', '=', self.group_id.zalo_id)]
        if manual and Message.search_count(domain + [('state', '=', 'uncertain')]):
            raise UserError('Có tin chưa rõ kết quả gửi trong ngày này. Hãy kiểm tra nhóm Zalo và lịch sử trước khi gửi thêm.')
        existing = Message.search(domain + [('send_mode', '=', 'manual' if manual else 'daily')]
            + ([('state', 'in', ['queued', 'failed'])] if manual else []), limit=1)
        if existing:
            return existing
        sessions = self.env['edu.session'].search_count([('date', '=', day), ('state', '!=', 'cancel')])
        if not sessions:
            raise UserError('Ngày này không có lịch học để gửi.')
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        identity = '%s|%s|%s' % (dbuuid, self.group_id.zalo_id, day)
        if manual:
            identity += '|manual|' + uuid.uuid4().hex
        key = hashlib.sha256(identity.encode()).hexdigest()
        return Message.create({'config_id': self.id, 'date': day, 'group_name': self.group_id.name,
            'group_zalo_id': self.group_id.zalo_id, 'content': self._schedule_text(day), 'request_key': key,
            'send_mode': 'manual' if manual else 'daily'})

    def action_send(self):
        self.ensure_one()
        self._manager()
        message = self._queue(self.preview_date, manual=True)
        self.env.ref('edu_zalo.cron_zalo_schedule')._trigger()
        return {'type': 'ir.actions.act_window', 'res_model': message._name, 'res_id': message.id,
            'view_mode': 'form', 'target': 'current'}

    def action_send_today(self):
        self.ensure_one()
        self._manager()
        today = datetime.now(TZ).date()
        message = self._queue(today, manual=True)
        self._deliver_messages(message)
        if message.state == 'sent':
            text = 'Đã gửi lịch hôm nay (%s) vào nhóm %s.' % (today.strftime('%d/%m/%Y'), message.group_name)
            kind = 'success'
        else:
            text = message.error or 'Chưa xác nhận kết quả gửi. Hãy kiểm tra lịch sử gửi Zalo.'
            kind = 'danger' if message.state == 'failed' else 'warning'
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': 'Gửi lịch học Zalo', 'message': text, 'type': kind,
            'sticky': message.state != 'sent'}}

    @api.model
    def _deliver_messages(self, messages):
        for message in messages.sudo():
            # Serialize the direct button and cron; the bridge also deduplicates after a DB rollback.
            self.env.cr.execute('SELECT id FROM edu_zalo_message WHERE id = %s FOR UPDATE', [message.id])
            message.invalidate_recordset()
            if message.state not in ('queued', 'failed'):
                continue
            try:
                result = self._bridge('POST', '/messages', {'key': message.request_key,
                    'group_id': message.group_zalo_id, 'parts': split_message(message.content), 'format': 'schedule-v1'})
                state = result.get('state')
                message.write({'state': 'sent' if state == 'sent' else 'uncertain',
                    'sent_at': fields.Datetime.now() if state == 'sent' else False,
                    'message_ids': ', '.join(result.get('message_ids', [])),
                    'error': False if state == 'sent' else 'Chưa xác nhận đủ tin đã gửi. Hãy kiểm tra nhóm Zalo trước khi gửi lại.'})
            except UserError as exc:
                message.write({'state': 'failed', 'error': str(exc)})

    @api.model
    def _cron_send(self):
        # Single worker per database; manual and automatic use the same unique daily key.
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s)', [77318201])
        if not self.env.cr.fetchone()[0]:
            return
        now = datetime.now(TZ)
        for config in self.search([('auto_send', '=', True)]):
            scheduled_minute = round(config.send_hour * 60) % 1440
            # Stay within the configured day's window; never send before its start.
            if 0 <= now.hour * 60 + now.minute - scheduled_minute < 30:
                with self.env.cr.savepoint():
                    if self.env['edu.session'].search_count([('date', '=', now.date()), ('state', '!=', 'cancel')]):
                        config._queue(now.date())
        messages = self.env['edu.zalo.message'].search([('state', '=', 'queued')], order='id', limit=5)
        self._deliver_messages(messages)


class EduSession(models.Model):
    _inherit = 'edu.session'

    def action_send_today_zalo(self):
        config = self.env.ref('edu_zalo.config_default')
        return config.action_send_today()


class ZaloMessage(models.Model):
    _name = 'edu.zalo.message'
    _description = 'Lịch sử gửi lịch Zalo'
    _order = 'id desc'
    _rec_name = 'date'

    config_id = fields.Many2one('edu.zalo.config', required=True, ondelete='restrict')
    date = fields.Date('Ngày lịch học', required=True, readonly=True)
    group_name = fields.Char('Nhóm nhận', required=True, readonly=True)
    group_zalo_id = fields.Char(required=True, readonly=True)
    content = fields.Text('Nội dung gửi', required=True, readonly=True)
    request_key = fields.Char(required=True, readonly=True, copy=False)
    send_mode = fields.Selection([('daily', 'Tự động'), ('manual', 'Thủ công')],
        string='Cách gửi', required=True, default='daily', readonly=True, index=True)
    state = fields.Selection([('queued', 'Chờ gửi'), ('sent', 'Đã gửi'), ('failed', 'Lỗi kết nối'),
        ('uncertain', 'Cần kiểm tra trên Zalo')], default='queued', required=True, readonly=True)
    sent_at = fields.Datetime('Gửi lúc', readonly=True)
    message_ids = fields.Char('Mã tin Zalo', readonly=True)
    error = fields.Text('Thông báo', readonly=True)
    _sql_constraints = [('request_key_unique', 'unique(request_key)', 'Yêu cầu gửi này đã có trong lịch sử.')]

    def init(self):
        # Keep old daily receipts and their bridge keys; only manual sends may repeat per day.
        self.env.cr.execute('ALTER TABLE edu_zalo_message DROP CONSTRAINT IF EXISTS edu_zalo_message_daily_group_unique')
        self.env.cr.execute('''CREATE UNIQUE INDEX IF NOT EXISTS edu_zalo_message_daily_group_once
            ON edu_zalo_message(date, group_zalo_id) WHERE send_mode = 'daily' ''')

    def action_retry(self):
        self.env['edu.zalo.config']._manager()
        for message in self:
            if message.state != 'failed':
                raise UserError('Chỉ thử lại khi lỗi kết nối. Tin chưa rõ kết quả cần đối chiếu trên Zalo.')
        self.sudo().write({'state': 'queued', 'error': False})
        self.env.ref('edu_zalo.cron_zalo_schedule')._trigger()
