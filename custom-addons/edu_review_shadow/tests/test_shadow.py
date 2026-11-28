import hashlib
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.edu_review_shadow.models import shadow as shadow_module

VIDEO = bytes(range(256)) * 4096          # 1 MiB fake video; never leaves the test
MD5 = hashlib.md5(VIDEO).hexdigest()


class Response:
    def __init__(self, status, body=None, data=b'', headers=None):
        self.status_code, self._body, self.raw = status, body, self
        self._data = data
        self.headers = headers or {'content-type': 'application/json'}

    def json(self):
        return self._body

    def read(self, n):
        return self._data[:n]

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeWorker:
    """Minimal in-memory model of the review worker API (same idempotency rules)."""

    def __init__(self):
        self.jobs, self.calls, self.lose_next = {}, [], set()

    def public(self, key):
        job = self.jobs[key]
        return {'key': key, 'state': job['state'], 'stage': job['state'], 'progress': 0, 'attempts': 0, 'error': None,
                'durations': {'1': 1800.0}, 'result': job.get('result'), 'metrics': job.get('metrics'),
                'parts': {str(p['number']): {'size': p['size'], 'received': len(job['data'][p['number']]),
                                             'verified': job['verified'][p['number']]} for p in job['spec']['parts']}}

    def __call__(self, record, method, path, **kwargs):
        self.calls.append((method, path))
        bits = path.strip('/').split('/')
        key = bits[2]
        if method == 'PUT' and len(bits) == 3:
            job = self.jobs.setdefault(key, {'spec': kwargs['json'], 'state': 'receiving',
                                             'data': {p['number']: b'' for p in kwargs['json']['parts']},
                                             'verified': {p['number']: False for p in kwargs['json']['parts']}})
            if job['spec'] != kwargs['json']:
                return Response(409, {'detail': 'spec_conflict'})
            response = Response(200, self.public(key))
        elif method == 'PUT':
            job, number = self.jobs[key], int(bits[4])
            start = int(kwargs['headers']['Content-Range'].split()[1].split('-')[0])
            if start != len(job['data'][number]):
                return Response(409, {'error': 'offset', 'received': len(job['data'][number])})
            job['data'][number] += kwargs['data']
            if len(job['data'][number]) == job['spec']['parts'][0]['size']:
                job['verified'][number] = True
            response = Response(200, self.public(key))
        elif method == 'POST' and bits[3] == 'start':
            if self.jobs[key]['state'] == 'receiving':
                self.jobs[key]['state'] = 'queued'
            response = Response(200, self.public(key))
        elif method == 'POST' and bits[3] == 'ack':
            response = Response(200, self.public(key))
        else:
            if key not in self.jobs:
                return Response(404, {'detail': 'job'})
            response = Response(200, self.public(key))
        if (method, path) in self.lose_next:  # the worker did the work but the answer never arrived
            self.lose_next.discard((method, path))
            raise shadow_module.ShadowError('worker_transport:ReadTimeout')
        return response


def fake_drive(record, file_id, resource_key, **kwargs):
    if kwargs.get('params', {}).get('alt') != 'media':
        return Response(200, {'size': str(len(VIDEO)), 'md5Checksum': MD5, 'mimeType': 'video/mp4',
                              'capabilities': {'canDownload': True}})
    start, end = map(int, kwargs['headers']['Range'][6:].split('-'))
    return Response(206, data=VIDEO[start:end + 1],
                    headers={'Content-Range': 'bytes %s-%s/%s' % (start, end, len(VIDEO))})


class ShadowBase(TransactionCase):
    def setUp(self):
        super().setUp()
        for target in ('odoo.addons.edu_review_shadow.models.shadow.requests.request',
                       'odoo.addons.edu_review_shadow.models.shadow.requests.get',
                       'odoo.addons.edu_session_review.models.review.requests.request'):
            guard = patch(target, side_effect=AssertionError('No network in tests'))
            guard.start()
            self.addCleanup(guard.stop)
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('edu_review_shadow.worker_url', 'http://worker.test:8090')
        params.set_param('edu_review_shadow.worker_token', 'test-token')
        params.set_param('edu_review_shadow.enabled_since', '2000-01-01 00:00:00')
        self.worker = FakeWorker()
        for name, fn in (('_worker', self.worker), ('_drive', fake_drive)):
            p = patch.object(type(self.env['edu.session.review.shadow']), name, autospec=True, side_effect=fn)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(shadow_module, 'CHUNK', 256 * 1024)
        p.start()
        self.addCleanup(p.stop)
        teacher = self.env['edu.teacher'].create({'name': 'SHADOW TEACHER'})
        student = self.env['edu.student'].create({'name_vi': 'Shadow One'})
        self.session = self.env['edu.session'].create({
            'date': '2052-03-01', 'teacher_id': teacher.id, 'time_start': 20, 'time_end': 20.5, 'state': 'done',
            'google_drive_url': 'https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz012345/view',
            'attendee_ids': [fields.Command.create({'student_id': student.id})]})
        self.review = self.env['edu.session.review'].create({
            'session_id': self.session.id, 'model_name': 'test', 'state': 'done', 'prompt_version': '2.1',
            'source_signature': self.session._review_signature(), 'roster_snapshot': self.session._review_roster(),
            'planned_minutes': 30, 'sufficient_data': True, 'total_minutes': 30, 'teaching_minutes': 24,
            'score_available': True, 'score_total': 7.0, 'finished_at': fields.Datetime.now()})
        self.Shadow = self.env['edu.session.review.shadow']

    def advance(self, row, budget=600):
        import time
        row._advance(time.monotonic() + budget)


@tagged('post_install', '-at_install')
class TestReviewShadow(ShadowBase):
    def test_enqueue_once_per_report_with_stable_key(self):
        first = self.Shadow._enqueue()
        self.assertEqual(first.review_id, self.review)
        self.assertFalse(self.Shadow._enqueue())
        self.assertEqual(first.job_key, self.Shadow.make_key(self.review, self.review.roster_snapshot))
        self.assertRegex(first.job_key, r'^kim-\d+-[0-9a-f]{16}$')

    def test_disabled_without_start_date_or_token(self):
        self.env['ir.config_parameter'].sudo().set_param('edu_review_shadow.enabled_since', False)
        self.assertFalse(self.Shadow._enqueue())
        self.env['ir.config_parameter'].sudo().set_param('edu_review_shadow.worker_token', False)
        self.Shadow._cron_run()
        self.assertFalse(self.worker.calls)

    def test_upload_resumes_and_lost_responses_never_duplicate(self):
        row = self.Shadow._enqueue()
        key = row.job_key
        self.advance(row, budget=-1)            # deadline reached before the first chunk
        self.assertEqual(row.state, 'upload')
        self.worker.lose_next.add(('POST', '/v1/jobs/%s/start' % key))
        self.advance(row)                       # uploads everything, start answer lost
        self.assertEqual(row.state, 'upload')
        self.assertEqual(row.failures, 1)
        self.assertEqual(self.worker.jobs[key]['state'], 'queued')
        row.next_check = False
        self.advance(row)                       # re-asks the worker: no byte re-sent, start is a no-op
        self.assertEqual(row.state, 'waiting')
        self.assertEqual(self.worker.jobs[key]['data'][1], VIDEO)
        uploads = [c for c in self.worker.calls if c[0] == 'PUT' and '/parts/' in c[1]]
        self.assertEqual(len(uploads), len(VIDEO) // shadow_module.CHUNK)
        self.assertEqual(len(self.worker.jobs), 1)

    def test_offset_conflict_resumes_at_worker_offset(self):
        row = self.Shadow._enqueue()
        part_path = '/v1/jobs/%s/parts/1' % row.job_key
        self.worker.lose_next.add(('PUT', part_path))   # first chunk stored, answer lost
        self.advance(row)
        row.next_check = False
        self.advance(row)
        self.assertEqual(self.worker.jobs[row.job_key]['data'][1], VIDEO)
        self.assertEqual(row.state, 'waiting')

    def test_done_result_is_stored_only_on_shadow(self):
        row = self.Shadow._enqueue()
        self.advance(row)
        job = self.worker.jobs[row.job_key]
        job.update(state='done', result={'summary': 'x'}, metrics={'wall_seconds': 600, 'peak_child_rss_mb': 5000})
        before = self.review.read(['score_total', 'teaching_minutes', 'summary', 'state'])
        values = {'score_available': True, 'score_total': 8.0, 'teaching_minutes': 26.5, 'total_minutes': 30,
                  'teaching_started_at': 'Phần 1 · 01:45', 'interaction_level': 'good', 'summary': 'Tóm tắt',
                  'student_report': 'Học sinh', 'student_alert_count': 0}
        with patch.object(shadow_module, 'validate_report', return_value=values):
            self.advance(row)
        self.assertEqual(row.state, 'done')
        self.assertTrue(row.acked)
        self.assertAlmostEqual(row.score_diff, 1.0)
        self.assertAlmostEqual(row.teaching_diff, 2.5)
        self.assertEqual(row.wall_minutes, 10)
        self.assertEqual(self.review.read(['score_total', 'teaching_minutes', 'summary', 'state']), before)

    def test_invalid_worker_result_fails_without_retry(self):
        row = self.Shadow._enqueue()
        self.advance(row)
        self.worker.jobs[row.job_key].update(state='done', result={})
        self.advance(row)
        self.assertEqual(row.state, 'failed')
        self.assertTrue(row.error.startswith('invalid_result'))
        with self.assertRaises(UserError):
            row.action_retry()

    def test_changed_drive_link_skips(self):
        row = self.Shadow._enqueue()
        self.session.google_drive_url = 'https://drive.google.com/file/d/1ZyXwVuTsRqPoNmLkJiHgFeDcBa98765/view'
        self.advance(row)
        self.assertEqual(row.state, 'skipped')
        self.assertFalse(self.worker.calls)


@tagged('post_install', '-at_install')
class TestOfficialWorkerReview(ShadowBase):
    """Sessions without a finished report get one official report from the worker."""

    VALUES = {'sufficient_data': True, 'score_available': True, 'score_total': 7.5, 'teaching_minutes': 26.5,
              'total_minutes': 30, 'teaching_percent': 88.3, 'teaching_started_at': 'Phần 1 · 01:45',
              'interaction_level': 'good', 'summary': 'Tóm tắt worker', 'quality_note': 'ASR',
              'interaction_comment': 'x', 'student_report': 'Học sinh', 'student_alert_count': 0,
              'student_report_available': True}

    def setUp(self):
        super().setUp()
        # The Gemini attempt sent the video and lost the answer: it must stay exactly as it is.
        self.review.write({'state': 'failed', 'analysis_started': True, 'error': 'ReadTimeout'})
        self.session.invalidate_recordset()

    def finish(self, row, **job):
        self.advance(row)
        self.assertEqual(row.state, 'waiting')
        self.worker.jobs[row.job_key].update(state='done', result={'summary': 'x'},
                                             metrics={'wall_seconds': 60, 'llm_usage': {'reduce_model': 'gemini-3.5-flash'}},
                                             **job)
        with patch.object(shadow_module, 'validate_report', return_value=dict(self.VALUES)):
            self.advance(row)

    def test_creates_one_done_report_and_keeps_failed_attempt(self):
        row = self.Shadow._queue_official()
        self.assertEqual((row.mode, row.session_id), ('official', self.session))
        self.assertFalse(self.Shadow._queue_official())
        self.finish(row)
        report = row.official_review_id
        self.assertEqual(report.state, 'done')
        self.assertEqual(report.model_name, 'kim-worker/gemini-3.5-flash')
        self.assertEqual(report.summary, 'Tóm tắt worker')
        self.assertEqual(report.part_ids.mapped('duration'), [1800.0])
        self.assertTrue(report.source_current)
        self.assertTrue(row.acked)
        self.session.invalidate_recordset()
        self.assertTrue(self.session.ai_review_done)
        self.assertEqual(self.session.ai_review_id, report)
        self.assertEqual(self.review.read(['state', 'analysis_started'])[0]['state'], 'failed')
        self.assertTrue(self.review.analysis_started)
        self.assertFalse(self.Shadow._queue_official())
        self.assertFalse(self.Shadow._enqueue().filtered(lambda r: r.review_id == report))

    def test_highlight_clips_are_published_outside_the_report_schema(self):
        self.session.youtube_url = 'https://youtu.be/AbCdEfGhIjK'
        row = self.Shadow._queue_official()
        self.advance(row)
        clips = [{'part': 1, 'start': '12:30', 'end': '15:10', 'reason': 'Hỏi đáp qua lại, sửa lỗi ngay.'},
                 {'part': 1, 'start': '20:00', 'end': '29:00', 'reason': 'quá 5 phút'},
                 {'part': 2, 'start': '01:00', 'end': '03:00', 'reason': 'không có phần 2'},
                 {'part': 1, 'start': '29:00', 'end': '31:00', 'reason': 'vượt thời lượng'}]
        self.worker.jobs[row.job_key].update(state='done', result={'summary': 'x', 'highlights': clips},
                                             metrics={'wall_seconds': 60})
        seen = []

        def validate(data, *args, **kwargs):
            seen.append(set(data))
            return dict(self.VALUES)
        with patch.object(shadow_module, 'validate_report', side_effect=validate):
            self.advance(row)
        self.assertEqual(seen, [{'summary'}, {'summary'}])        # stored result and publish: key removed
        report = row.official_review_id
        self.assertEqual(report.highlight_count, 1)
        self.assertEqual(report.highlight_clips,
                         '1. Phần 1 · 12:30 → 15:10 (2 phút 40 giây)\n   Hỏi đáp qua lại, sửa lỗi ngay.')
        self.assertIn('watch?v=AbCdEfGhIjK&amp;t=750s', report.highlight_html)
        self.assertEqual(report.result_json['highlights'], clips)  # raw worker output kept for audit
        self.session.invalidate_recordset()
        self.assertEqual(self.session.ai_review_highlight_html, report.highlight_html)
        domain = eval(self.env.ref('edu_review_shadow.action_review_highlight').domain)  # noqa: S307 - own XML
        self.assertIn(report, self.env['edu.session.review'].search(domain))

    def test_old_worker_result_without_highlights_is_unchanged(self):
        data = {'summary': 'x'}
        self.assertIs(shadow_module.split_highlights(data, {1: 1800.0})[0], data)
        self.assertEqual(shadow_module.split_highlights(data, {1: 1800.0})[1], {})
        row = self.Shadow._queue_official()
        self.finish(row)
        self.assertFalse(row.official_review_id.highlight_count)
        self.assertFalse(row.official_review_id.highlight_html)

    def test_find_highlights_adds_clips_to_a_finished_report_only(self):
        self.review.write({'state': 'done', 'analysis_started': False, 'error': False})
        self.session.invalidate_recordset()
        before = self.review.read(['score_total', 'summary', 'model_name', 'state'])
        self.session.action_find_highlights()
        self.session.action_find_highlights()                  # second press: same run, no duplicate
        rows = self.Shadow.search([('mode', '=', 'highlight')])
        self.assertEqual(len(rows), 1)
        row = rows
        self.assertEqual((row.target_review_id, row.priority), (self.review, True))
        self.assertIn('Tìm đoạn nổi bật', self.session.ai_highlight_status)
        self.assertFalse(self.Shadow._queue_official())       # the session already has a report
        self.advance(row)
        clips = [{'part': 1, 'start': '05:00', 'end': '07:30', 'reason': 'Học sinh trả lời thành câu.'}]
        self.worker.jobs[row.job_key].update(state='done', result={'summary': 'x', 'highlights': clips},
                                             metrics={'wall_seconds': 60})
        with patch.object(shadow_module, 'validate_report', return_value=dict(self.VALUES)):
            self.advance(row)
        self.assertEqual((row.state, row.fallback_note, row.acked), ('done', 'attached:1', True))
        self.assertFalse(row.official_review_id)
        self.assertEqual(self.review.highlight_count, 1)
        self.assertIn('05:00 → 07:30', self.review.highlight_html)
        self.assertEqual(self.review.read(['score_total', 'summary', 'model_name', 'state']), before)
        self.assertEqual(self.env['edu.session.review'].search_count([('session_id', '=', self.session.id)]), 1)
        self.Shadow._fallback_gemini()                          # never a Gemini fallback for this mode
        self.assertFalse(row.fallback_review_id)
        self.session.action_find_highlights()                  # pressed again later: a new run (new key)
        self.assertEqual(len(self.Shadow.search([('mode', '=', 'highlight')])), 2)

    def test_find_highlights_checks_the_report_and_its_videos(self):
        with self.assertRaises(UserError):                     # report not done
            self.session.action_find_highlights()
        self.review.write({'state': 'done'})
        self.session.invalidate_recordset()
        self.session.action_find_highlights()
        row = self.Shadow.search([('mode', '=', 'highlight')])
        self.advance(row)
        self.worker.jobs[row.job_key].update(state='done', result={'summary': 'x', 'highlights': [
            {'part': 1, 'start': '05:00', 'end': '07:30', 'reason': 'r'}]}, metrics={'wall_seconds': 60})
        self.review.source_signature = 'changed'               # report no longer describes these videos
        with patch.object(shadow_module, 'validate_report', return_value=dict(self.VALUES)):
            self.advance(row)
        self.assertEqual(row.fallback_note, 'not_attached:review_changed')
        self.assertFalse(self.review.highlight_count)
        self.session.invalidate_recordset()
        with self.assertRaises(UserError):                     # source no longer current
            self.session.action_find_highlights()

    def test_not_published_when_another_report_finished_first(self):
        row = self.Shadow._queue_official()
        self.review.state = 'done'
        self.finish(row)
        self.assertFalse(row.official_review_id)
        self.assertEqual(row.error, 'not_published:already_reviewed')
        self.assertTrue(row.acked)
        self.assertEqual(self.env['edu.session.review'].search_count([('session_id', '=', self.session.id)]), 1)

    def test_publish_waits_for_gemini_sequential_lock(self):
        row = self.Shadow._queue_official()
        with self.registry.cursor() as other:
            other.execute('SELECT pg_advisory_lock(87425, 0)')
            try:
                self.finish(row)
                self.assertFalse(row.official_review_id)
                self.assertFalse(row.acked)
                self.assertEqual(row.state, 'done')
            finally:
                other.execute('SELECT pg_advisory_unlock(87425, 0)')
        with patch.object(shadow_module, 'validate_report', return_value=dict(self.VALUES)):
            self.advance(row)
        self.assertTrue(row.official_review_id)
        self.assertTrue(row.acked)

    def test_strictly_one_session_on_the_worker(self):
        other = self.session.copy({'date': '2052-03-02', 'state': 'done', 'google_drive_url': 'https://drive.google.com/file/d/1QwErTyUiOpAsDfGhJkLzXcVbNm098765/view'})
        self.assertNotEqual(other._review_signature(), False)
        rows = self.Shadow._queue_official()
        self.assertEqual(len(rows), 2)
        with patch.object(type(self.env.cr), 'commit', lambda cr: None):
            self.Shadow._cron_run()
            first, second = rows.sorted('id')
            self.assertEqual((first.state, second.state), ('waiting', 'upload'))
            self.Shadow._cron_run()
            self.assertEqual(second.state, 'upload')
            self.assertFalse([c for c in self.worker.calls if second.job_key in c[1]])


@tagged('post_install', '-at_install')
class TestWorkerPriority(ShadowBase):
    """Kim Worker is the primary provider once prefer_worker_since is set; Gemini is the fallback."""

    VALUES = TestOfficialWorkerReview.VALUES
    finish = TestOfficialWorkerReview.finish

    def setUp(self):
        super().setUp()
        self.config = self.env.ref('edu_video.config_default').sudo()
        self.config.write({'processing_enabled': False, 'review_enabled': True, 'review_auto': True,
                           'review_execution': 'sync', 'review_api_key': 'fake-key', 'drive_state': 'connected',
                           'refresh_token': 'fake-drive'})
        # Rejected before inference (no lost response): a fallback may create a new attempt.
        self.review.write({'state': 'failed', 'analysis_started': False, 'error': 'HTTP 400'})
        self.session.invalidate_recordset()
        since = fields.Datetime.now() + timedelta(hours=1)   # everything created in the test is "before"
        self.set_since(fields.Datetime.to_string(since))
        self.env.user.groups_id |= self.env.ref('edu_gvnn.group_edu_manager')
        self.Review = self.env['edu.session.review'].sudo()

    def set_since(self, value):
        self.env['ir.config_parameter'].sudo().set_param('edu_review_shadow.prefer_worker_since', value)

    def gemini(self, **values):
        return self.Review.create(dict({
            'session_id': self.session.id, 'model_name': 'gemini-test', 'state': 'queued', 'prompt_version': '2.1',
            'source_signature': self.session._review_signature(), 'roster_snapshot': self.session._review_roster(),
            'planned_minutes': 30}, **values))

    def reviews(self):
        return self.Review.search([('session_id', '=', self.session.id)])

    def upload_queue(self):
        return self.Shadow.search([('state', '=', 'upload')]).sorted(self.Shadow._run_order)

    def test_drive_change_no_longer_queues_gemini(self):
        before = self.reviews()
        self.session.google_drive_url = 'https://drive.google.com/file/d/1ZyXwVuTsRqPoNmLkJiHgFeDcBa98765/view'
        self.assertEqual(self.reviews(), before)
        self.set_since(False)
        self.session.google_drive_url = 'https://drive.google.com/file/d/1QwErTyUiOpAsDfGhJkLzXcVbNm098765/view'
        self.assertEqual(len(self.reviews() - before), 1)   # unchanged Gemini behaviour when switched off

    def test_unsent_auto_gemini_request_is_taken_over(self):
        queued = self.gemini()
        row = self.Shadow._queue_official()
        self.assertEqual(row.session_id, self.session)
        self.assertEqual(queued.state, 'cancelled')
        self.assertTrue(queued.cleanup_pending)
        self.assertFalse(queued.analysis_started)
        self.assertEqual(self.review.state, 'failed')

    def test_started_immediate_or_new_gemini_requests_keep_the_session(self):
        for values in ({'state': 'analyzing', 'analysis_started': True},
                       {'immediate_until': fields.Datetime.now() + timedelta(hours=1)}):
            with self.subTest(values=values):
                run = self.gemini(**values)
                self.assertFalse(self.Shadow._queue_official())
                self.assertIn(run.state, ('queued', 'analyzing'))
                run.state = 'cancelled'
        self.set_since('2000-01-01 00:00:00')
        manual = self.gemini()   # created after the switch: a manager asked Gemini explicitly
        self.assertFalse(self.Shadow._queue_official())
        self.assertEqual(manual.state, 'queued')

    def test_takeover_waits_for_the_gemini_cron(self):
        queued = self.gemini()
        with self.registry.cursor() as other:
            other.execute('SELECT pg_advisory_lock(87425, 0)')
            try:
                self.assertFalse(self.Shadow._queue_official())
                self.assertEqual(queued.state, 'queued')
            finally:
                other.execute('SELECT pg_advisory_unlock(87425, 0)')

    def test_failed_worker_run_falls_back_to_one_gemini_request(self):
        row = self.Shadow._queue_official()
        self.advance(row)
        self.worker.jobs[row.job_key]['state'] = 'failed'
        self.advance(row)
        self.assertEqual(row.state, 'failed')
        before = self.reviews()
        self.Shadow._fallback_gemini()
        new = self.reviews() - before
        self.assertEqual(len(new), 1)
        self.assertEqual((row.fallback_note, row.fallback_review_id), ('gemini_queued', new))
        self.assertEqual(new.state, 'queued')
        self.Shadow._fallback_gemini()
        self.assertEqual(self.reviews() - before, new)
        self.assertFalse(self.Shadow._queue_official())   # the same video never goes back to the worker
        self.assertEqual(self.review.state, 'failed')

    def test_no_fallback_after_a_lost_gemini_response(self):
        self.review.write({'analysis_started': True})
        row = self.Shadow._queue_official()
        row.write({'state': 'failed', 'error': 'worker:asr'})
        before = self.reviews()
        self.Shadow._fallback_gemini()
        self.assertEqual(row.fallback_note, 'unknown_gemini_attempt')
        self.assertEqual(self.reviews(), before)

    def test_publish_waits_for_an_open_gemini_run(self):
        row = self.Shadow._queue_official()
        manual = self.gemini(immediate_until=fields.Datetime.now() + timedelta(hours=1))
        self.finish(row)
        self.assertEqual((row.state, row.error, row.acked), ('done', 'publish_wait:gemini_in_progress', False))
        self.assertFalse(row.official_review_id)
        self.session.invalidate_recordset()
        self.assertIn('chờ lượt Gemini', self.session.ai_worker_status)
        manual.write({'state': 'failed'})
        row.next_check = False
        with patch.object(shadow_module, 'validate_report', return_value=dict(self.VALUES)):
            self.advance(row)
        self.assertEqual(row.official_review_id.state, 'done')
        self.assertTrue(row.acked)
        self.assertFalse(row.error)

    def test_analyze_button_sends_the_session_to_the_worker_first(self):
        other = self.session.copy({'date': '2052-02-01', 'state': 'done', 'google_drive_url':
                                   'https://drive.google.com/file/d/1QwErTyUiOpAsDfGhJkLzXcVbNm098765/view'})
        first = self.Shadow._queue_official(other)
        self.assertTrue(first)
        before = self.reviews()
        action = self.session.action_analyze_lesson()
        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(self.reviews(), before)      # no Gemini request
        row = self.Shadow.search([('session_id', '=', self.session.id)])
        self.assertTrue(row.priority)
        self.assertEqual(self.upload_queue()[:2].ids, [row.id, first.id])
        self.session.invalidate_recordset()
        self.assertIn('ưu tiên', self.session.ai_worker_status)
        self.session.action_analyze_lesson()          # pressing again creates nothing new
        self.assertEqual(self.Shadow.search_count([('session_id', '=', self.session.id)]), 1)
        self.assertEqual(self.reviews(), before)

    def test_analyze_button_uses_gemini_after_the_worker_failed(self):
        row = self.Shadow._queue_official()
        row.write({'state': 'failed', 'error': 'worker:asr', 'fallback_checked': True})
        before = self.reviews()
        self.session.action_analyze_lesson()
        self.assertEqual(len(self.reviews() - before), 1)

    # ---- worker Gemini text quota (25/11/2026): never a reason to fall back to Gemini video
    def quota_failed(self, **values):
        row = self.Shadow._queue_official()
        row.write(dict({'state': 'failed', 'error': 'worker:LLMError:gemini_http_429'}, **values))
        return row

    def test_quota_failure_runs_again_on_the_worker_instead_of_gemini(self):
        row = self.quota_failed()
        before = self.reviews()
        self.Shadow._fallback_gemini()
        self.assertEqual(row.fallback_note, 'quota_requeue')
        self.assertEqual(self.reviews(), before)
        again = self.Shadow._requeue_quota_failures()
        self.assertEqual((again.session_id, again.state, again.mode), (self.session, 'upload', 'official'))
        self.assertNotEqual(again.job_key, row.job_key)        # the worker never reruns a failed job key
        self.assertEqual(row.fallback_note, 'requeued')
        self.assertFalse(self.Shadow._requeue_quota_failures())
        self.assertFalse(self.Shadow._queue_official())
        self.assertEqual(self.reviews(), before)
        self.session.invalidate_recordset()
        self.assertIn('Kim Worker: đang chờ', self.session.ai_worker_status)

    def test_requeue_cancels_the_unsent_fallback_gemini_request(self):
        row = self.quota_failed()
        fallback = self.gemini()      # what the old code created after the quota failure
        row.write({'fallback_checked': True, 'fallback_note': 'gemini_queued', 'fallback_review_id': fallback.id})
        again = self.Shadow._requeue_quota_failures()
        self.assertTrue(again)
        self.assertEqual((fallback.state, fallback.cleanup_pending), ('cancelled', True))
        self.assertFalse(fallback.analysis_started)
        self.assertEqual(row.fallback_note, 'requeued:gemini_cancelled')

    def test_requeue_leaves_a_sent_gemini_request_and_waits_for_the_lock(self):
        row = self.quota_failed()
        sent = self.gemini(state='analyzing', analysis_started=True)
        row.fallback_review_id = sent
        self.assertFalse(self.Shadow._requeue_quota_failures())
        self.assertEqual(sent.state, 'analyzing')
        sent.write({'state': 'failed'})
        unsent = self.gemini()
        row.fallback_review_id = unsent
        with self.registry.cursor() as other:
            other.execute('SELECT pg_advisory_lock(87425, 0)')
            try:
                self.assertFalse(self.Shadow._requeue_quota_failures())
                self.assertEqual(unsent.state, 'queued')
            finally:
                other.execute('SELECT pg_advisory_unlock(87425, 0)')

    def test_non_quota_worker_errors_still_fall_back(self):
        row = self.quota_failed(error='worker:LLMError:gemini_http_400')
        self.assertFalse(self.Shadow._requeue_quota_failures())
        self.Shadow._fallback_gemini()
        self.assertEqual(row.fallback_note, 'gemini_queued')

    def test_quota_wait_status_and_analyze_button_requeue(self):
        row = self.Shadow._queue_official()
        row.write({'state': 'waiting', 'worker_stage': 'quota_wait'})
        self.session.invalidate_recordset()
        self.assertIn('hạn mức Gemini', self.session.ai_worker_status)
        row.write({'state': 'failed', 'error': 'worker:LLMError:gemini_http_429'})
        before = self.reviews()
        self.session.action_analyze_lesson()
        self.assertEqual(self.reviews(), before)               # no Gemini request
        again = self.Shadow.search([('session_id', '=', self.session.id)], order='id desc', limit=1)
        self.assertEqual((again.state, again.priority), ('upload', True))
        self.session.action_analyze_lesson()                   # pressing again: same row
        self.assertEqual(self.Shadow.search_count([('session_id', '=', self.session.id)]), 2)

    def test_cron_queues_new_sessions_by_itself(self):
        with patch.object(type(self.env.cr), 'commit', lambda cr: None):
            self.Shadow._cron_run()
        row = self.Shadow.search([('session_id', '=', self.session.id)])
        self.assertEqual((row.mode, row.state), ('official', 'waiting'))
