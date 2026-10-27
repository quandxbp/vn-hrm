import hashlib
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import requests

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from ..models.job import parse_drive_url, TransferError


def response(status=200, body=None, headers=None, content=b''):
    result = requests.Response()
    result.status_code = status
    result.headers.update(headers or {})
    result._content = content if body is None else json.dumps(body).encode()
    result._content_consumed = True
    return result


@tagged('post_install', '-at_install')
class TestVideoTransfer(TransactionCase):
    def setUp(self):
        super().setUp()
        self.config = self.env.ref('edu_video.config_default').sudo()
        self.config.write({'state': 'connected', 'drive_state': 'connected',
            'channel_id': 'channel-target', 'channel_handle': '@YUYONG90',
            'expected_channel_handle': '@YUYONG90',
            'access_token': 'fake-drive-token', 'refresh_token': 'fake-drive-refresh',
            'expires_at': time.time() + 3600, 'youtube_access_token': 'fake-youtube-token',
            'youtube_refresh_token': 'fake-youtube-refresh', 'youtube_expires_at': time.time() + 3600,
            'processing_enabled': False, 'auto_upload': False})
        self.env['edu.week'].create({'number': 99890, 'date_from': '2030-01-01', 'date_to': '2030-01-07'})
        teacher = self.env['edu.teacher'].create({'name': 'Video Transfer Test Teacher', 'teaching_title': 'mr'})
        student = self.env['edu.student'].create({'name_vi': 'Video Transfer Test Student', 'name_en': 'Alex'})
        self.session = self.env['edu.session'].create({'teacher_id': teacher.id,
            'date': '2030-01-02', 'time_start': 17.5, 'time_end': 18,
            'google_drive_url': 'https://drive.google.com/file/d/test_file_123456/view',
            'attendee_ids': [(0, 0, {'student_id': student.id})]})
        self.job = self.session._enqueue_video()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'video.tmp'
        Job = type(self.job)
        patcher = patch.object(Job, '_path', return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(Job, '_checkpoint')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_drive_urls_reject_untrusted_and_folders(self):
        self.assertEqual(parse_drive_url(self.session.google_drive_url), ('test_file_123456', ''))
        self.assertEqual(parse_drive_url('https://drive.google.com/open?id=test_file_123456&resourcekey=key1'),
                         ('test_file_123456', 'key1'))
        for url in ['http://127.0.0.1/video', 'https://drive.google.com.evil.test/file/d/test_file_123456/view',
                    'https://drive.google.com/drive/folders/test_file_123456',
                    'https://evil@drive.google.com/file/d/test_file_123456/view',
                    'https://drive.google.com:bad/open?id=test_file_123456']:
            with self.assertRaises(UserError):
                parse_drive_url(url)

    def test_enqueue_is_idempotent_and_does_not_replace_youtube(self):
        self.assertEqual(self.session._enqueue_video(), self.job)
        with self.assertRaises(UserError):
            self.session.google_drive_url = 'https://drive.google.com/file/d/another_file_12345/view'
        self.session.youtube_url = 'https://youtu.be/existing123'
        with self.assertRaises(UserError):
            self.session._enqueue_video()
        self.job.write({'total_bytes': 3})
        self.job._complete({'id': 'newvideo123'})
        self.assertEqual(self.session.youtube_url, 'https://youtu.be/existing123')
        self.assertEqual(self.job.video_url, 'https://youtu.be/newvideo123')

    def test_multipart_jobs_complete_into_the_correct_part(self):
        part = self.env['edu.session.recording.part'].create({
            'session_id': self.session.id, 'number': 2,
            'google_drive_url': 'https://drive.google.com/file/d/part_two_file_12345/view'})
        jobs = self.session._enqueue_video()
        self.assertEqual(len(jobs), 2)
        second = jobs.filtered('recording_part_id')
        self.assertEqual(second.recording_part_id, part)
        self.assertTrue(second.title.endswith('(WEEK 99890) (2)'))
        self.assertEqual(self.session._enqueue_video(), jobs)
        second._complete({'id': 'parttwovide'})
        self.assertEqual(part.youtube_url, 'https://youtu.be/parttwovide')
        self.assertFalse(self.session.youtube_url)
        self.assertEqual(self.session.video_state, 'queued')
        self.job._complete({'id': 'partonevide'})
        self.assertEqual(self.session.youtube_url, 'https://youtu.be/partonevide')
        self.assertEqual(part.youtube_url, 'https://youtu.be/parttwovide')
        self.assertFalse(self.session.video_upload_pending)
        self.assertEqual(self.session.video_state, 'done')

    def test_second_part_is_queued_even_when_first_is_uploaded(self):
        self.session.youtube_url = 'https://youtu.be/existing123'
        part = self.env['edu.session.recording.part'].create({
            'session_id': self.session.id, 'number': 2,
            'google_drive_url': 'https://drive.google.com/file/d/part_two_file_12345/view'})
        self.assertTrue(self.session.video_upload_pending)
        jobs = self.session._enqueue_video()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs.recording_part_id, part)
        with self.assertRaises(UserError):
            part.unlink()
        with self.assertRaises(UserError):
            part.google_drive_url = 'https://drive.google.com/file/d/replaced_part_12345/view'

    def test_auto_enqueue_additional_part_is_independent(self):
        self.config.auto_upload = True
        self.session.youtube_url = 'https://youtu.be/existing123'
        part = self.env['edu.session.recording.part'].create({
            'session_id': self.session.id, 'number': 2,
            'google_drive_url': 'https://drive.google.com/file/d/auto_part_two_12345/view'})
        jobs = self.env['edu.video.job'].search([('recording_part_id', '=', part.id)])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs.source_url, part.google_drive_url)

    @patch('odoo.addons.edu_video.models.job.requests.request')
    def test_cron_end_to_end_public_not_for_kids_and_separate_tokens(self, request):
        content = b'fake video data'
        request.side_effect = [
            response(body={'size': str(len(content)), 'mimeType': 'video/mp4',
                'md5Checksum': hashlib.md5(content).hexdigest(), 'capabilities': {'canDownload': True}}),
            response(206, content=content, headers={'Content-Range': 'bytes 0-%s/%s' % (len(content)-1, len(content))}),
            response(body={'items': [{'id': 'channel-target'}]}),
            response(headers={'Location': 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=fake'}),
            response(308), response(200, body={'id': 'testvideo12'}),
        ]
        self.config.processing_enabled = True
        self.env['edu.video.job']._cron_process()
        self.assertEqual(self.job.state, 'done')
        self.assertEqual(self.session.youtube_url, 'https://youtu.be/testvideo12')
        self.assertFalse(self.path.exists())
        self.assertFalse(self.job.upload_url)
        init = request.call_args_list[3]
        self.assertEqual(init.kwargs['json']['status']['privacyStatus'], 'public')
        self.assertIs(init.kwargs['json']['status']['selfDeclaredMadeForKids'], False)
        self.assertIn('17:30', init.kwargs['json']['snippet']['description'])
        self.assertIn('02/01/2030', init.kwargs['json']['snippet']['description'])
        self.assertIn('Thứ Tư', init.kwargs['json']['snippet']['description'])
        self.assertEqual(init.kwargs['params']['notifySubscribers'], 'false')
        self.assertEqual(request.call_args_list[0].kwargs['headers']['Authorization'], 'Bearer fake-drive-token')
        self.assertEqual(init.kwargs['headers']['Authorization'], 'Bearer fake-youtube-token')

    @patch('odoo.addons.edu_video.models.job.requests.request')
    def test_resume_uses_server_offset_and_never_creates_new_upload(self, request):
        self.path.write_bytes(b'abcdef')
        self.job.write({'state': 'uploading', 'total_bytes': 6, 'mime_type': 'video/mp4',
            'upload_url': 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=fake',
            'channel_id': 'channel-target'})
        request.side_effect = [response(308, headers={'Range': 'bytes=0-2'}),
                               response(body={'id': 'resumetest1'})]
        self.job._step()
        self.assertEqual(request.call_args_list[1].kwargs['data'], b'def')
        self.assertEqual(request.call_args_list[1].kwargs['headers']['Content-Range'], 'bytes 3-5/6')
        self.assertTrue(all(call.args[0] == 'PUT' for call in request.call_args_list))
        self.assertEqual(self.job.state, 'done')

    @patch('odoo.addons.edu_video.models.job.requests.request')
    def test_expired_upload_requires_review(self, request):
        self.job.write({'state': 'uploading', 'total_bytes': 6,
            'upload_url': 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=fake',
            'channel_id': 'channel-target'})
        request.return_value = response(404)
        self.config.processing_enabled = True
        self.env['edu.video.job']._cron_process()
        self.assertEqual(self.job.state, 'uncertain')
        self.assertTrue(self.job.upload_url)
        with self.assertRaises(UserError):
            self.job.action_retry()

    @patch('odoo.addons.edu_video.models.job.requests.request')
    def test_timeout_keeps_session_for_retry(self, request):
        self.job.write({'state': 'uploading', 'total_bytes': 6,
            'upload_url': 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=fake'})
        request.side_effect = requests.Timeout('sensitive URL must not be logged')
        self.config.processing_enabled = True
        self.env['edu.video.job']._cron_process()
        self.assertEqual(self.job.state, 'uploading')
        self.assertEqual(self.job.attempts, 1)
        self.assertTrue(self.job.upload_url)
        self.assertNotIn('sensitive', self.job.error)

    @patch('odoo.addons.edu_video.models.job.requests.request')
    def test_drive_download_denial(self, request):
        request.return_value = response(body={'capabilities': {'canDownload': False}})
        with self.assertRaises(TransferError):
            self.job._metadata(self.config)
        self.assertFalse(self.path.exists())

    def test_auto_enqueue_only_future_changes_and_processing_disabled(self):
        self.assertFalse(self.config.auto_upload)
        self.config.auto_upload = True
        session = self.session.copy({'google_drive_url': False, 'youtube_url': False})
        self.assertFalse(session.video_job_ids)
        session.google_drive_url = 'https://drive.google.com/file/d/auto_file_12345/view'
        self.assertEqual(len(session.video_job_ids), 1)
        with patch('odoo.addons.edu_video.models.job.requests.request') as request:
            self.env['edu.video.job']._cron_process()
            request.assert_not_called()

    def test_deployment_callback_validation(self):
        self.config.redirect_uri = 'https://odoo.example.com/edu-video/google/callback'
        for invalid in ['http://odoo.example.com/edu-video/google/callback', 'https://odoo.example.com/wrong']:
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.config.redirect_uri = invalid

    def test_background_link_update_after_payroll_lock(self):
        self.session.write({'paid': True})
        self.job._complete({'id': 'paidvideo12'})
        self.assertEqual(self.session.youtube_url, 'https://youtu.be/paidvideo12')
        self.assertTrue(self.session.paid)

    @patch('odoo.addons.edu_video.models.job.requests.request')
    def test_completed_remote_session_after_lost_final_response(self, request):
        self.job.write({'state': 'uploading', 'total_bytes': 6,
            'upload_url': 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=fake',
            'channel_id': 'channel-target'})
        request.return_value = response(body={'id': 'recovered12'})
        self.job._step()
        self.assertEqual(self.job.state, 'done')
        self.assertEqual(self.session.youtube_url, 'https://youtu.be/recovered12')
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0], 'PUT')

    @patch('odoo.addons.edu_video.models.job.requests.request')
    def test_checksum_error_never_uploads(self, request):
        self.job.write({'state': 'downloading', 'total_bytes': 3, 'checksum': hashlib.md5(b'abc').hexdigest()})
        self.path.write_bytes(b'xyz')
        with self.assertRaises(TransferError):
            self.job._step()
        request.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_restart_requires_stopped_job_and_does_not_overwrite_link(self):
        with self.assertRaises(UserError):
            self.job.action_restart_checked()
        self.job.write({'state': 'uncertain', 'upload_url': 'https://www.googleapis.com/upload/fake'})
        self.job.action_restart_checked()
        self.assertEqual(self.job.state, 'queued')
        self.assertFalse(self.job.upload_url)
        self.job.write({'state': 'uncertain'})
        self.session.youtube_url = 'https://youtu.be/existing123'
        with self.assertRaises(UserError):
            self.job.action_restart_checked()

    @patch('odoo.addons.edu_video.models.config.requests.post')
    def test_refresh_keeps_drive_and_youtube_credentials_separate(self, post):
        self.config.write({'youtube_expires_at': 0})
        post.return_value = response(body={'access_token': 'renewed-youtube', 'expires_in': 3600})
        self.assertEqual(self.config._token('youtube'), 'renewed-youtube')
        self.assertEqual(post.call_args.kwargs['data']['refresh_token'], 'fake-youtube-refresh')
        self.assertEqual(self.config.access_token, 'fake-drive-token')

    def test_nonmanager_cannot_control_jobs(self):
        with self.assertRaises(UserError):
            self.job.with_user(self.env.ref('base.public_user')).action_cancel()
        with self.assertRaises(UserError):
            self.session.with_user(self.env.ref('base.public_user')).action_upload_youtube()
