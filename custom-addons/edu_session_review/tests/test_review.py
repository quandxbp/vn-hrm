import copy
import hashlib
import io
import json
import tempfile
import requests
from pathlib import Path
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from ..models.report import validate_report
from ..models.review import API, CHUNK, ReviewError, safe_upload_url


def response(data=None, status=200, headers=None, raw=b''):
    result = MagicMock(status_code=status, headers=headers or {}, raw=io.BytesIO(raw))
    result.json.return_value = data or {}
    result.__enter__.return_value = result
    return result


def report():
    return {
        'summary': 'Buổi học hướng dẫn rõ ràng.', 'sufficient_data': True, 'quality_note': '',
        'interaction_level': 'good', 'interaction_comment': 'Học sinh được thực hành.',
        'parts': [{'part': 1, 'teaching_segments': [{'start': 10, 'end': 50}, {'start': 60, 'end': 100}]}],
        'strengths': [{'comment': 'Sửa lỗi và cho thử lại.', 'evidence': [{'part': 1, 'start': 20, 'end': 30}]}],
        'improvements': [{'comment': 'Rút ngắn phần chuẩn bị.', 'evidence': [{'part': 1, 'start': 0, 'end': 10}]}],
    }


@tagged('post_install', '-at_install')
class TestSessionReview(TransactionCase):
    def setUp(self):
        super().setUp()
        self.config = self.env.ref('edu_video.config_default').sudo()
        self.config.write({'auto_upload': False, 'processing_enabled': False, 'review_enabled': True,
            'review_auto': False, 'review_api_key': 'fake-key', 'drive_state': 'connected', 'refresh_token': 'fake-drive'})
        teacher = self.env['edu.teacher'].create({'name': 'Review Test Teacher'})
        self.session = self.env['edu.session'].create({'date': '2051-02-01', 'teacher_id': teacher.id,
            'google_drive_url': 'https://drive.google.com/file/d/review_source_1234/view',
            'youtube_url': 'https://youtu.be/alreadydone'})
        self.review = self.session._queue_ai_review()
        self.part = self.review.part_ids
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'test.video'
        patcher = patch.object(type(self.part), '_path', return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(type(self.review), '_checkpoint')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_report_totals_and_evidence(self):
        values = validate_report(report(), {1: 120})
        self.assertAlmostEqual(values['teaching_minutes'], 80 / 60)
        self.assertAlmostEqual(values['teaching_percent'], 80 / 120 * 100)
        self.assertIn('Phần 1 00:20–00:30', values['strengths'])

    def test_report_rejects_overlap_nan_missing_and_bad_evidence(self):
        for mutate in (
            lambda d: d['parts'][0]['teaching_segments'].append({'start': 40, 'end': 80}),
            lambda d: d['parts'][0]['teaching_segments'].append({'start': 100, 'end': float('nan')}),
            lambda d: d['parts'].clear(),
            lambda d: d['strengths'][0]['evidence'][0].update(part=2),
            lambda d: d['strengths'][0]['evidence'][0].update(end=121),
        ):
            data = report()
            mutate(data)
            with self.assertRaises(UserError):
                validate_report(data, {1: 120})

    def test_insufficient_data_does_not_fabricate_timing(self):
        data = report()
        data.update(sufficient_data=False, quality_note='Mất âm thanh.', interaction_level='insufficient')
        values = validate_report(data, {1: 120})
        self.assertFalse(values['sufficient_data'])
        self.assertEqual(values['teaching_percent'], 0)

    def test_multiple_parts_all_required(self):
        data = report()
        data['parts'].append({'part': 3, 'teaching_segments': [{'start': 0, 'end': 60}]})
        values = validate_report(data, {1: 120, 3: 60})
        self.assertAlmostEqual(values['teaching_percent'], 140 / 180 * 100)

    def test_manual_duplicate_and_new_version_existing_youtube(self):
        self.assertEqual(self.session._queue_ai_review(force=True), self.review)
        self.review.state = 'done'
        self.assertEqual(self.session._queue_ai_review(), self.review)
        new = self.session._queue_ai_review(force=True)
        self.assertNotEqual(new, self.review)
        self.assertEqual(self.session.youtube_url, 'https://youtu.be/alreadydone')

    def test_auto_new_sources_and_stale_reports(self):
        self.config.review_auto = True
        self.session.google_drive_url = 'https://drive.google.com/file/d/review_other_12345/view'
        self.assertFalse(self.review.source_current)
        self.assertEqual(self.review.state, 'cancelled')
        current = self.session.ai_review_id
        self.assertTrue(current.source_current)
        count = len(self.session.ai_review_ids)
        self.session.note = 'Attendance edit must not queue analysis.'
        self.assertEqual(len(self.session.ai_review_ids), count)

    def test_additional_drive_part_queues_complete_snapshot(self):
        self.config.review_auto = True
        self.env['edu.session.recording.part'].create({'session_id': self.session.id, 'number': 2,
            'google_drive_url': 'https://drive.google.com/file/d/review_second_12345/view'})
        self.assertEqual(self.session.ai_review_id.part_ids.mapped('number'), [1, 2])

    def test_bad_source_does_not_break_session_write(self):
        self.config.review_auto = True
        self.session.google_drive_url = 'not-a-drive-link'
        self.assertEqual(self.session.google_drive_url, 'not-a-drive-link')
        self.assertEqual(len(self.session.ai_review_ids), 1)

    def test_permissions_private_results_and_key(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Review Staff', 'login': 'review-staff',
            'groups_id': [fields.Command.set([self.env.ref('edu_gvnn.group_edu_staff').id])],
        })
        with self.assertRaises(AccessError):
            self.session.with_user(user).action_analyze_lesson()
        with self.assertRaises(AccessError):
            self.review.with_user(user).read(['summary'])
        with self.assertRaises(AccessError):
            self.review.with_user(user).action_cancel()
        admin = self.env.ref('base.user_admin')
        with self.assertRaises(AccessError):
            self.config.with_user(admin).read(['review_api_key'])
        self.assertFalse(self.config.with_user(admin).review_key_input)

    def test_download_is_bounded_and_checksum_checked(self):
        content = b'test-video'
        self.part.write({'total_bytes': len(content), 'checksum': hashlib.md5(content).hexdigest(), 'mime_type': 'video/mp4'})
        with patch.object(type(self.part), '_drive', return_value=response(
                status=206, headers={'Content-Range': 'bytes 0-9/10'}, raw=content)):
            self.assertTrue(self.part._download())
        self.assertEqual(self.path.read_bytes(), content)
        self.part._download()
        self.assertEqual(self.part.state, 'upload')
        self.path.write_bytes(b'bad-bytes!')
        with self.assertRaises(UserError):
            self.part._download()

    def test_download_rejects_wrong_range_and_oversize(self):
        self.part.write({'total_bytes': 10, 'checksum': 'unused'})
        for status, headers, data in [(200, {}, b'1234567890'),
                (206, {'Content-Range': 'bytes 0-9/10'}, b'12345678901')]:
            with patch.object(type(self.part), '_drive', return_value=response(status=status, headers=headers, raw=data)):
                with self.assertRaises(UserError):
                    self.part._download()
        self.assertFalse(self.path.exists())

    def test_upload_url_rejects_redirect_targets(self):
        for value in ('http://generativelanguage.googleapis.com/upload/foo', 'https://evil.test/upload/foo',
                      'https://generativelanguage.googleapis.com.evil.test/upload/foo'):
            with self.assertRaises(UserError):
                safe_upload_url(value)

    def test_resumable_upload_uses_server_offset_and_file_metadata(self):
        self.path.write_bytes(b'abcdefghij')
        self.part.write({'state': 'upload', 'total_bytes': 10, 'mime_type': 'video/mp4',
                         'upload_url': API + '/upload/v1beta/files?upload_id=fake'})
        with patch.object(type(self.review), '_gemini', side_effect=[
            response(headers={'X-Goog-Upload-Status': 'active', 'X-Goog-Upload-Size-Received': '4'}),
            response({'file': {'name': 'files/test-file', 'uri': API + '/v1beta/files/test-file'}}),
        ]) as call:
            self.part._upload()
        self.assertEqual(call.call_args.kwargs['data'], b'efghij')
        self.assertEqual(call.call_args.kwargs['extra_headers']['X-Goog-Upload-Offset'], '4')
        self.assertEqual(self.part.state, 'waiting')
        self.assertFalse(self.path.exists())

    def test_finalized_upload_recovers_file_without_reupload(self):
        self.part.write({'state': 'upload', 'upload_url': API + '/upload/v1beta/files?upload_id=fake'})
        with patch.object(type(self.review), '_gemini', side_effect=[
            response(headers={'X-Goog-Upload-Status': 'final'}),
            response({'files': [{'name': 'files/test-file', 'uri': API + '/v1beta/files/test-file',
                                 'displayName': self.part._display_name()}]}),
        ]) as call:
            self.part._upload()
        self.assertEqual(self.part.state, 'waiting')
        self.assertEqual(call.call_count, 2)

    def test_processing_polls_without_waiting_and_uses_actual_duration(self):
        self.part.write({'state': 'waiting', 'gemini_name': 'files/test-file'})
        with patch.object(type(self.review), '_gemini', return_value=response({'state': 'PROCESSING'})):
            self.assertFalse(self.part._step())
        with patch.object(type(self.review), '_gemini', return_value=response({
                'state': 'ACTIVE', 'videoMetadata': {'videoDuration': '120.5s'}})):
            self.part._step()
        self.assertEqual(self.part.duration, 120.5)

    def test_analysis_and_safe_report(self):
        self.review.state = 'analyzing'
        self.part.write({'state': 'ready', 'total_bytes': 10, 'duration': 120, 'gemini_uri': API + '/v1beta/files/test-file', 'mime_type': 'video/mp4'})
        with patch.object(type(self.review), '_gemini', return_value=response({
                'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(report())}]}}]})) as call:
            self.review._step()
        self.assertIn(':generateContent', call.call_args.args[1])
        self.assertNotIn(self.session.google_drive_url, json.dumps(call.call_args.kwargs['json']))
        self.assertEqual(self.review.state, 'done')
        self.assertTrue(self.review.cleanup_pending)

    def test_unconfirmed_analysis_is_not_submitted_again(self):
        self.review.state = 'analyzing'
        self.part.write({'state': 'ready', 'total_bytes': 10, 'duration': 120})
        self.review.analysis_started = True
        with patch.object(type(self.review), '_gemini') as call:
            with self.assertRaises(UserError):
                self.review._step()
        call.assert_not_called()

    def test_cleanup_only_deletes_review_files(self):
        self.path.write_bytes(b'temporary')
        unrelated = self.path.parent / 'youtube-cache.video'
        unrelated.write_bytes(b'keep')
        self.part.gemini_name = 'files/test-file'
        self.review.write({'state': 'done', 'cleanup_pending': True})
        with patch.object(type(self.review), '_gemini', return_value=response()):
            self.review._cleanup()
        self.assertFalse(self.path.exists())
        self.assertEqual(unrelated.read_bytes(), b'keep')
        self.assertFalse(self.review.cleanup_pending)

    def test_disabled_and_neutralized_workers_never_send(self):
        with patch.object(type(self.review), '_gemini') as call:
            self.config.review_enabled = False
            self.review._cron_process()
            self.config.review_enabled = True
            self.env['ir.config_parameter'].sudo().set_param('database.is_neutralized', 'True')
            self.review._cron_process()
        call.assert_not_called()

    def test_no_configuration_blocks_manual_but_not_normal_edits(self):
        self.config.review_enabled = False
        self.session.note = 'Safe without Gemini.'
        with self.assertRaises(UserError):
            self.session.action_analyze_lesson()

    def test_known_overload_can_retry_but_lost_analysis_response_cannot(self):
        self.review.state = 'analyzing'
        self.part.write({'state': 'ready', 'total_bytes': 10, 'duration': 120})
        with patch.object(type(self.review), '_gemini', side_effect=ReviewError('HTTP 503', retry=True)):
            with self.assertRaises(ReviewError):
                self.review._step()
        self.assertFalse(self.review.analysis_started)
        with patch.object(type(self.review), '_gemini', side_effect=requests.Timeout()):
            # Odoo's assertRaises rolls back a savepoint, while the real worker
            # checkpoints this flag before making the request.
            try:
                self.review._step()
            except requests.Timeout:
                pass
            else:
                self.fail('Expected timeout')
        self.assertTrue(self.review.analysis_started)

    def test_worker_success_and_failure_preserve_video_upload(self):
        self.env['ir.config_parameter'].sudo().set_param('database.is_neutralized', 'False')
        def finish(record):
            record.state = 'done'
            return True
        with patch.object(type(self.review), '_step', autospec=True, side_effect=finish):
            self.review._cron_process()
        self.assertEqual(self.review.state, 'done')
        self.assertEqual(self.session.youtube_url, 'https://youtu.be/alreadydone')
        self.review.state = 'queued'
        with patch.object(type(self.review), '_step', side_effect=ReviewError('Transient', retry=True)):
            self.review._cron_process()
        self.assertEqual(self.review.state, 'queued')
        self.assertTrue(self.review.next_attempt)

    def test_expired_jobs_cleanup_even_when_analysis_disabled(self):
        self.config.review_enabled = False
        self.path.write_bytes(b'old cache')
        self.env.cr.execute("UPDATE edu_session_review SET create_date='2000-01-01' WHERE id=%s", [self.review.id])
        self.review.invalidate_recordset(['create_date'])
        self.review._cron_cleanup()
        self.assertEqual(self.review.state, 'failed')
        self.assertFalse(self.path.exists())
