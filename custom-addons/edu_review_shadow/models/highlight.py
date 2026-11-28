"""Best teaching clips (2–5 minutes) chosen by Kim Worker, for managers to cut and post themselves.

The worker sends an optional ``highlights`` list next to the report (part, start, end MM:SS, reason).
It is never part of the Gemini report schema: ``split_highlights`` removes it before
``validate_report`` and an invalid clip is dropped instead of failing the whole review.
"""
import re

from markupsafe import Markup

from odoo import api, fields, models
from odoo.addons.edu_session_review.models.report import clock, timestamp

CLIP_MIN, CLIP_MAX, CLIP_LIMIT = 30, 330, 3
YOUTUBE_ID = re.compile(r'(?:youtu\.be/|[?&]v=|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{11})')


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


def split_highlights(data, durations):
    """(report without 'highlights', field values for edu.session.review)."""
    if not isinstance(data, dict) or 'highlights' not in data:
        return data, {}
    report = {k: v for k, v in data.items() if k != 'highlights'}
    clips = clean_highlights(data.get('highlights'), durations)
    return report, {'highlight_count': len(clips), 'highlight_clips': highlight_text(clips) or False}


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


class SessionReviewHighlight(models.Model):
    _inherit = 'edu.session.review'

    highlight_count = fields.Integer('Số đoạn nổi bật', readonly=True, copy=False)
    highlight_clips = fields.Text('Đoạn dạy nổi bật', readonly=True, copy=False)
    highlight_html = fields.Html('Đoạn dạy nổi bật (xem thử)', compute='_compute_highlight_html', sanitize=True)

    @api.depends('highlight_count', 'result_json', 'part_ids.duration', 'session_id.youtube_url',
                 'session_id.recording_part_ids.youtube_url')
    def _compute_highlight_html(self):
        for review in self:
            durations = {part.number: part.duration for part in review.part_ids}
            clips = clean_highlights((review.result_json or {}).get('highlights'), durations) \
                if review.highlight_count and isinstance(review.result_json, dict) else []
            if not clips:
                review.highlight_html = False
                continue
            youtube = {source['number']: source['youtube'] for source in review.session_id._recording_parts()}
            rows = []
            for index, (part, start, end, reason) in enumerate(clips, 1):
                link = youtube_at(youtube.get(part), start)
                rows.append(Markup(
                    '<li><strong>Phần %s · %s → %s</strong> <span class="text-muted">(%s)</span>%s%s</li>') % (
                    part, clock(start), clock(end), duration_text(end - start),
                    Markup(' · <a href="%s" target="_blank" rel="noopener noreferrer">Xem trên YouTube từ %s</a>') % (
                        link, clock(start)) if link else '',
                    Markup('<br/><span>%s</span>') % reason if reason else ''))
            review.highlight_html = Markup('<ol class="mb-0">%s</ol>') % Markup('').join(rows)


class SessionHighlight(models.Model):
    _inherit = 'edu.session'

    ai_review_highlight_html = fields.Html(related='ai_review_id.highlight_html', string='Đoạn dạy nổi bật',
                                           groups='edu_gvnn.group_edu_manager')
