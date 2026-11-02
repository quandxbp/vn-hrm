"""Read-only Odoo shell audit; never calls Google or submits/retries a review.

Usage on the target host (select the actual database explicitly):
  Get-Content -Raw -Encoding UTF8 scripts/ops/inspect_ai_reviews.py |
    docker compose exec -T web odoo shell -d kimacademy --no-http --max-cron-threads=0

Output deliberately excludes credentials, names, video URLs and provider responses.
"""
import collections
import json

from odoo import fields


def inspect(env):
    params = env['ir.config_parameter'].sudo()
    receipt = json.loads(params.get_param('edu_session_review.protocol_recovery_20261102', '{}'))
    ids = receipt.get('upload_review_ids', [])
    if receipt.get('replacement_review_id'):
        ids = ids + [receipt['replacement_review_id']]
    Review = env['edu.session.review'].sudo()
    rows = Review.browse(ids).exists()
    latest = {}
    for review in Review.search([], order='id desc'):
        latest.setdefault(review.session_id.id, review)
    config = env.ref('edu_video.config_default').sudo()
    cron = env.ref('edu_session_review.cron_review')
    module = env['ir.module.module'].sudo().search([('name', '=', 'edu_session_review')], limit=1)
    return {
        'checked_at_utc': str(fields.Datetime.now()),
        'database': env.cr.dbname,
        'module_version': module.installed_version,
        'neutralized': params.get_param('database.is_neutralized'),
        'review_enabled': config.review_enabled,
        'review_auto': config.review_auto,
        'video_processing_enabled': config.processing_enabled,
        'cron_active': cron.active,
        'cron_nextcall_utc': str(cron.nextcall),
        'latest_per_session_states': dict(collections.Counter(r.state for r in latest.values())),
        'recovery_count': len(rows),
        'recovery_states': dict(collections.Counter(rows.mapped('state'))),
        'approved_replacement': {
            'source_id': receipt.get('authorized_source_review'),
            'replacement_id': receipt.get('replacement_review_id'),
        },
        'recovery_details': [{
            'id': r.id, 'session_id': r.session_id.id, 'state': r.state,
            'stage': r.last_stage, 'error_stage': r.last_error_stage,
            'error_type': r.last_error_type, 'attempts': r.attempts,
            'next_attempt_utc': str(r.next_attempt),
            'analysis_started': r.analysis_started,
            'saved_result': bool(r.result_json),
            'parts': [{'number': p.number, 'state': p.state,
                       'uploaded_bytes': p.uploaded_bytes, 'total_bytes': p.total_bytes}
                      for p in r.part_ids],
        } for r in rows],
    }


try:
    print(json.dumps(inspect(env), ensure_ascii=True, default=str))
finally:
    env.cr.rollback()
