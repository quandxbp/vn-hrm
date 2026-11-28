"""Best teaching clips (2–5 minutes) chosen by Kim Worker, for managers to cut and post themselves.

The worker sends an optional ``highlights`` list next to the report (part, start, end MM:SS, reason).
It is never part of the Gemini report schema: ``split_highlights`` removes it before
``validate_report`` and an invalid clip is dropped instead of failing the whole review.

Clips arrive two ways:
- a new worker report (official mode) carries them;
- 'Tìm đoạn nổi bật' (mode ``highlight``, approved 28/11/2026) runs the worker on an already finished
  report's videos and attaches only the clips to THAT report. Its scores and comments are untouched,
  no report is created and a failed run never falls back to Gemini.
"""
import hashlib
import json
import re

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.addons.edu_session_review.models.report import clock, timestamp

CLIP_MIN, CLIP_MAX, CLIP_LIMIT = 30, 330, 3
YOUTUBE_ID = re.compile(r'(?:youtu\.be/|[?&]v=|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{11})')
STAGES = {'asr': 'nhận dạng giọng nói', 'frames': 'đọc khung hình', 'visual': 'đọc khung hình',
          'synthesis': 'chọn đoạn', 'queued': 'chờ worker', 'receiving': 'nhận video',
          'quota_wait': 'chờ hạn mức Gemini miễn phí của ngày mới (khoảng 15:00)'}


def clean_highlights(items, durations):
    """[(part, start_s, end_s, reason)] for well-formed clips; anything doubtful is dropped."""
    out = []
    for item in items if isinstance(items, list) else []:
        try:
            part, start, end = item['part'], timestamp(item['start']), timestamp(item['end'])
        except (KeyError, TypeError, ValueError):
            continue
        reason = item.get('reason') if isinstance(item.get('reason'), str) else ''
        if type(part) is not int or part not in durations or not 0 <= start < end <= durations[part] \
                or not CLIP_MIN <= end - start <= CLIP_MAX:
            continue
        out.append((part, int(start), int(end), ' '.join(reason.split())[:400]))
        if len(out) == CLIP_LIMIT:
            break
    return out


def highlight_values(clips):
    return {'highlight_count': len(clips), 'highlight_clips': highlight_text(clips) or False,
            'highlight_json': [{'part': p, 'start': clock(s), 'end': clock(e), 'reason': r}
                               for p, s, e, r in clips] or False}


def split_highlights(data, durations):
    """(report without 'highlights', field values for edu.session.review)."""
    if not isinstance(data, dict) or 'highlights' not in data:
        return data, {}
    report = {k: v for k, v in data.items() if k != 'highlights'}
    return report, highlight_values(clean_highlights(data.get('highlights'), durations))


def duration_text(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return ('%d phút %02d giây' % (minutes, seconds)) if minutes else '%d giây' % seconds


def highlight_text(clips):
    return '\n\n'.join('%d. Phần %d · %s → %s (%s)%s' % (
        index, part, clock(start), clock(end), duration_text(end - start), ('\n   ' + reason) if reason else '')
        for index, (part, start, end, reason) in enumerate(clips, 1))


def youtube_at(url, seconds):
    match = YOUTUBE_ID.search(url or '')
    return 'https://www.youtube.com/watch?v=%s&t=%ds' % (match.group(1), seconds) if match else False


def make_highlight_key(review, signature, roster, planned, run):
    payload = json.dumps([review.session_id.id, review.id, signature, roster, round(planned, 3), '2.1', run],
                         ensure_ascii=True, sort_keys=True)
    return 'kim-%s-%s' % (review.session_id.id, hashlib.sha256(('highlight|' + payload).encode()).hexdigest()[:16])


class SessionReviewHighlight(models.Model):
    _inherit = 'edu.session.review'

    highlight_count = fields.Integer('Số đoạn nổi bật', readonly=True, copy=False)
    highlight_clips = fields.Text('Đoạn dạy nổi bật', readonly=True, copy=False)
    highlight_json = fields.Json('Đoạn nổi bật (dữ liệu)', readonly=True, copy=False)
    highlight_html = fields.Html('Đoạn dạy nổi bật (xem thử)', compute='_compute_highlight_html', sanitize=True)

    @api.depends('highlight_json', 'session_id.youtube_url', 'session_id.recording_part_ids.youtube_url')
    def _compute_highlight_html(self):
        for review in self:
            clips = []
            for item in review.highlight_json if isinstance(review.highlight_json, list) else []:
                try:
                    clips.append((int(item['part']), timestamp(item['start']), timestamp(item['end']),
                                  str(item.get('reason') or '')))
                except (KeyError, TypeError, ValueError):
                    continue
            if not clips:
                review.highlight_html = False
                continue
            youtube = {source['number']: source['youtube'] for source in review.session_id._recording_parts()}
            rows = []
            for part, start, end, reason in clips:
                link = youtube_at(youtube.get(part), int(start))
                rows.append(Markup(
                    '<li><strong>Phần %s · %s → %s</strong> <span class="text-muted">(%s)</span>%s%s</li>') % (
                    part, clock(start), clock(end), duration_text(end - start),
                    Markup(' · <a href="%s" target="_blank" rel="noopener noreferrer">Xem trên YouTube từ %s</a>') % (
                        link, clock(start)) if link else '',
                    Markup('<br/><span>%s</span>') % reason if reason else ''))
            review.highlight_html = Markup('<ol class="mb-0">%s</ol>') % Markup('').join(rows)

    def action_find_highlights(self):
        self.ensure_one()
        return self.session_id._find_highlights(self)


class SessionHighlight(models.Model):
    _inherit = 'edu.session'

    ai_review_highlight_html = fields.Html(related='ai_review_id.highlight_html', string='Đoạn dạy nổi bật',
                                           groups='edu_gvnn.group_edu_manager')
    ai_highlight_status = fields.Char('Tìm đoạn nổi bật', compute='_compute_ai_highlight_status', compute_sudo=True,
                                      groups='edu_gvnn.group_edu_manager')

    def _compute_ai_highlight_status(self):
        Shadow = self.env['edu.session.review.shadow'].sudo()
        rows = Shadow.search([('mode', '=', 'highlight'), ('session_id', 'in', self.ids)], order='id desc') \
            if self.ids else Shadow
        for session in self:
            row = rows.filtered(lambda r: r.session_id == session)[:1]
            status = False
            if row.state == 'upload':
                queue = Shadow.search([('state', '=', 'upload')]).sorted(Shadow._run_order)
                ahead = list(queue).index(row) + Shadow.search_count([('state', '=', 'waiting')])
                status = 'Tìm đoạn nổi bật: đang chờ Kim Worker (còn %s buổi phía trước).' % ahead
            elif row.state == 'waiting':
                status = 'Kim Worker đang tìm đoạn nổi bật: %s, %s%%.' % (
                    STAGES.get(row.worker_stage, row.worker_stage or 'đang xử lý'), round((row.worker_progress or 0) * 100))
            elif row.state in ('failed', 'skipped'):
                status = 'Tìm đoạn nổi bật chưa xong (%s). Có thể bấm lại.' % (row.error or row.state)
            elif row.state == 'done' and row.fallback_note == 'none':
                status = 'Kim Worker không tìm thấy đoạn 2–5 phút đủ tốt trong buổi này.'
            elif row.state == 'done' and (row.fallback_note or '').startswith('not_attached'):
                status = 'Đã tìm đoạn nhưng không gắn vào nhận xét vì nhận xét hoặc video đã thay đổi. Có thể bấm lại.'
            session.ai_highlight_status = status

    def action_find_highlights(self):
        self.ensure_one()
        return self._find_highlights(self.sudo().ai_review_id)

    def _find_highlights(self, review):
        """Queue one worker run that only adds clips to `review` (a finished report of this session)."""
        self.ensure_one()
        if not self.env.user.has_group('edu_gvnn.group_edu_manager'):
            raise AccessError('Chỉ quản lý GVNN được tìm đoạn nổi bật.')
        self.check_access_rights('read')
        self.check_access_rule('read')
        review = review.sudo()
        if not review or review.session_id != self or review.state != 'done':
            raise UserError('Cần một nhận xét AI đã hoàn tất của buổi học này.')
        if not review.source_current:
            raise UserError('Video, danh sách học sinh hoặc thời lượng đã thay đổi so với nhận xét. '
                            'Hãy phân tích lại trước khi tìm đoạn nổi bật.')
        Shadow = self.env['edu.session.review.shadow'].sudo()
        Shadow._ready()
        sources = self._review_sources()
        if not sources or len(sources) > 10:
            raise UserError('Cần từ 1 đến 10 link Drive để tìm đoạn nổi bật.')
        runs = Shadow.search([('mode', '=', 'highlight'), ('target_review_id', '=', review.id)], order='id desc')
        if not runs.filtered(lambda r: r.state in ('upload', 'waiting')):
            roster, planned, signature = self._review_roster(), Shadow._planned(self), self._review_signature()
            Shadow.create({'mode': 'highlight', 'session_id': self.id, 'target_review_id': review.id, 'priority': True,
                           'job_key': make_highlight_key(review, signature, roster, planned, len(runs)),
                           'roster_json': roster, 'source_signature': signature, 'planned_minutes': planned})
        self.invalidate_recordset(['ai_highlight_status'])
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'type': 'info', 'title': 'Tìm đoạn nổi bật',
            'message': self.ai_highlight_status or 'Đã gửi buổi học cho Kim Worker.',
            'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}}}
