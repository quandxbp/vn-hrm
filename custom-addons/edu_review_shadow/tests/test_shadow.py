import hashlib
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
