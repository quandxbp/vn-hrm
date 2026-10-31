import io
from unittest.mock import patch

import requests
from PIL import Image

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from .test_transfer import response
from ..models.job import TransferError
from ..models.optimization import render_thumbnail


@tagged('post_install', '-at_install')
class TestVideoOptimization(TransactionCase):
    def setUp(self):
        super().setUp()
        self.config = self.env.ref('edu_video.config_default').sudo()
        self.config.write({'auto_upload': False, 'processing_enabled': False,
                           'channel_id': 'opt-channel', 'auto_thumbnail': True, 'auto_playlist': True,
                           'youtube_scopes': 'https://www.googleapis.com/auth/youtube.force-ssl'})
        self.week = self.env['edu.week'].create({
            'number': 99892, 'date_from': '2050-02-07', 'date_to': '2050-02-13'})
        self.teacher = self.env['edu.teacher'].create({'name': 'Optimization Test Hope', 'teaching_title': 'ms'})
        self.student = self.env['edu.student'].create({'name_vi': 'Optimization Test', 'name_en': 'Kelly'})
        self.session = self.env['edu.session'].create({
            'date': '2050-02-07', 'teacher_id': self.teacher.id, 'time_start': 17.5, 'time_end': 18,
            'google_drive_url': 'https://drive.google.com/file/d/opt_test_first_12345/view',
            'attendee_ids': [(0, 0, {'student_id': self.student.id})]})
        self.job = self.session._enqueue_video()
        self.job.write({'state': 'done', 'channel_id': 'opt-channel', 'video_url': 'https://youtu.be/optvideo123',
                        'optimization_state': 'pending', 'optimization_teacher_id': self.teacher.id})
        # Keep all network/file tests transactional, including checkpoints used for recovery.
        patcher = patch.object(type(self.job), '_checkpoint')
        patcher.start()
        self.addCleanup(patcher.stop)

    def channel(self, channel_id='opt-channel'):
        return response(body={'items': [{'id': channel_id}]})

    def playlist(self):
        return {'id': 'PLopt1234567890', 'snippet': {
            'channelId': 'opt-channel', 'title': self.job._playlist_title(),
            'description': self.job._playlist_description()}}

    def test_full_optimization_and_repeat_do_not_duplicate_or_upload_video(self):
        self.job.video_url = 'https://youtu.be/optvideo123'
        with patch.object(type(self.job), '_request', side_effect=[
                self.channel(), response(body={'items': [{}]}), response(body={'items': []}),
                response(body={'id': 'PLopt1234567890'}), response(body={'items': []}),
                response(body={'id': 'item-opt-1'})]) as request:
            self.job._optimize_uploaded_video(self.config)
        self.assertEqual(self.job.optimization_state, 'done')
        self.assertTrue(self.job.thumbnail_applied)
        self.assertEqual(self.job.playlist_item_id, 'item-opt-1')
        self.assertEqual(self.job.state, 'done')
        thumbnail_call = request.call_args_list[1]
        with Image.open(io.BytesIO(thumbnail_call.kwargs['data'])) as image:
            self.assertEqual(image.size, (3840, 2160))
            self.assertEqual(image.format, 'JPEG')
        self.assertLess(len(thumbnail_call.kwargs['data']), 2 * 1024 ** 2)
        self.assertEqual(request.call_args_list[3].kwargs['json']['snippet']['title'], 'KIMENGLISH - MS OPTIMIZATION TEST HOPE')
        self.assertEqual(request.call_args_list[3].kwargs['json']['status']['privacyStatus'], 'public')
        self.assertEqual(request.call_args_list[-1].kwargs['json']['snippet']['resourceId']['videoId'], 'optvideo123')
        self.assertFalse(any('/videos' in call.args[2] for call in request.call_args_list))
        with patch.object(type(self.job), '_request', return_value=self.channel()) as request:
            self.job._optimize_uploaded_video(self.config)
        self.assertEqual(request.call_count, 1)

    def test_old_oauth_scope_keeps_thumbnail_and_reports_playlist_reconnect(self):
        self.job.video_url = 'https://youtu.be/optvideo123'
        self.config.youtube_scopes = False
        with patch.object(type(self.job), '_request', side_effect=[self.channel(), response()]):
            self.job._optimize_uploaded_video(self.config)
        self.assertTrue(self.job.thumbnail_applied)
        self.assertEqual(self.job.state, 'done')
        self.assertEqual(self.job.optimization_state, 'failed')
        self.assertIn('kết nối lại YouTube', self.job.optimization_error)
        self.assertTrue(self.job.video_url)

    def test_pagination_reuses_playlist_and_existing_item(self):
        self.job.video_url = 'https://youtu.be/optvideo123'
        self.config.auto_thumbnail = False
        existing_playlist = self.playlist()
        existing_playlist['snippet']['description'] = 'Description edited in YouTube Studio'
        with patch.object(type(self.job), '_request', side_effect=[self.channel(),
                response(body={'items': [], 'nextPageToken': 'page-2'}),
                response(body={'items': [existing_playlist]}),
                response(body={'items': [{'id': 'already-added'}]})]) as request:
            self.job._optimize_uploaded_video(self.config)
        self.assertEqual(self.job.optimization_state, 'done')
        self.assertEqual(self.job.playlist_item_id, 'already-added')
        self.assertEqual(request.call_args_list[2].kwargs['params']['pageToken'], 'page-2')
        self.assertTrue(all(call.args[1] == 'GET' for call in request.call_args_list))

    def test_lost_playlist_response_is_recovered_without_another_creation(self):
        with patch.object(type(self.job), '_request', side_effect=[
                response(body={'items': []}), requests.Timeout('test-only timeout')]):
            # TransactionCase.assertRaises rolls back DB/cache changes; the worker catches
            # network errors without rollback so it retains the ambiguous-create marker.
            try:
                self.job._find_or_create_playlist(self.config)
            except requests.Timeout:
                pass
            else:
                self.fail('Expected a lost playlist response')
        self.assertTrue(self.job.playlist_create_pending)
        with patch.object(type(self.job), '_request', return_value=response(body={'items': []})) as request:
            with self.assertRaises(UserError):
                self.job._find_or_create_playlist(self.config)
            self.assertEqual(request.call_count, 1)
        with patch.object(type(self.job), '_request', return_value=response(body={'items': [self.playlist()]})) as request:
            self.assertEqual(self.job._find_or_create_playlist(self.config), 'PLopt1234567890')
            self.assertEqual(request.call_count, 1)
        self.assertFalse(self.job.playlist_create_pending)

    def test_lost_item_response_is_checked_before_another_insert(self):
        self.job.playlist_id = 'PLopt1234567890'
        with patch.object(type(self.job), '_request', side_effect=[
                response(body={'items': []}), requests.Timeout('test-only timeout')]):
            with self.assertRaises(requests.Timeout):
                self.job._add_to_playlist(self.config, 'optvideo123')
        with patch.object(type(self.job), '_request', return_value=response(body={'items': [{'id': 'recovered-item'}]})) as request:
            self.job._add_to_playlist(self.config, 'optvideo123')
            self.assertEqual(request.call_count, 1)
        self.assertEqual(self.job.playlist_item_id, 'recovered-item')

    def test_parts_are_inserted_adjacent_even_if_second_part_completes_first(self):
        part = self.env['edu.session.recording.part'].create({
            'session_id': self.session.id, 'number': 2,
            'google_drive_url': 'https://drive.google.com/file/d/opt_test_second_12345/view'})
        second = self.session._enqueue_video().filtered('recording_part_id')
        self.assertEqual(second.recording_part_id, part)
        second.write({'state': 'done', 'channel_id': 'opt-channel', 'video_url': 'https://youtu.be/second12345',
                      'playlist_id': 'PLopt1234567890', 'playlist_item_id': 'second-item'})
        self.job.playlist_id = second.playlist_id
        with patch.object(type(self.job), '_request', side_effect=[response(body={'items': []}),
                response(body={'items': [{'id': 'second-item', 'snippet': {'position': 6}}]}),
                response(body={'id': 'first-item'})]) as request:
            self.job._add_to_playlist(self.config, 'optvideo123')
        self.assertEqual(request.call_args_list[-1].kwargs['json']['snippet']['position'], 6)
        self.job.playlist_item_id = 'first-item'
        second.playlist_item_id = False
        with patch.object(type(self.job), '_request', side_effect=[response(body={'items': []}),
                response(body={'items': [{'id': 'first-item', 'snippet': {'position': 6}}]}),
                response(body={'id': 'second-item'})]) as request:
            second._add_to_playlist(self.config, 'second12345')
        self.assertEqual(request.call_args_list[-1].kwargs['json']['snippet']['position'], 7)

    def test_wrong_channel_stops_before_remote_changes(self):
        self.job.video_url = 'https://youtu.be/optvideo123'
        with patch.object(type(self.job), '_request', return_value=self.channel('other-channel')) as request:
            with self.assertRaises(UserError):
                self.job._optimize_uploaded_video(self.config)
        self.assertEqual(request.call_count, 1)
        self.assertFalse(self.job.thumbnail_applied)

    def test_retry_is_separate_from_upload_and_restricted_to_manager(self):
        self.job.optimization_state = 'failed'
        self.job.action_retry_optimization()
        self.assertEqual(self.job.state, 'done')
        self.assertEqual(self.job.optimization_state, 'pending')
        self.job.optimization_state = 'failed'
        with self.assertRaises(UserError):
            self.job.with_user(self.env.ref('base.public_user')).action_retry_optimization()

    def test_completed_upload_queues_optimization_and_existing_jobs_are_skipped(self):
        self.job.write({'state': 'uploading', 'optimization_state': 'skipped'})
        with patch.object(type(self.job), '_cleanup'):
            self.job._complete({'id': 'optvideo123'})
        self.assertEqual(self.job.optimization_state, 'pending')
        self.assertEqual(self.job.optimization_teacher_id, self.teacher)
        self.assertEqual(self.session.youtube_url, 'https://youtu.be/optvideo123')
        self.assertEqual(self.env['edu.video.job']._fields['optimization_state'].default(self.job), 'skipped')

    def test_cron_disabled_makes_no_requests(self):
        with patch.object(type(self.job), '_request') as request:
            self.env['edu.video.job']._cron_optimize()
            request.assert_not_called()

    def test_thumbnail_failure_does_not_block_playlist(self):
        self.job.video_url = 'https://youtu.be/optvideo123'
        with patch.object(type(self.job), '_request', side_effect=[self.channel(),
                requests.Timeout('test-only timeout'), response(body={'items': [self.playlist()]}),
                response(body={'items': [{'id': 'saved-item'}]})]):
            self.job._optimize_uploaded_video(self.config)
        self.assertEqual(self.job.playlist_item_id, 'saved-item')
        self.assertFalse(self.job.thumbnail_applied)
        self.assertEqual(self.job.optimization_state, 'pending')
        self.assertTrue(self.job.optimization_next_attempt)
        self.assertEqual(self.job.state, 'done')

    def test_temporary_playlist_404_retries_known_playlist_without_creating_another(self):
        self.job.thumbnail_applied = True
        self.job.playlist_id = 'PLopt1234567890'
        with patch.object(type(self.job), '_request', side_effect=[self.channel(),
                TransferError('Playlist not ready', status=404, reason='playlistNotFound')]):
            self.job._optimize_uploaded_video(self.config)
        self.assertEqual(self.job.optimization_state, 'pending')
        self.assertEqual(self.job.optimization_attempts, 1)
        self.assertTrue(self.job.optimization_next_attempt)
        with patch.object(type(self.job), '_request', side_effect=[self.channel(),
                response(body={'items': []}),response(body={'id': 'added-after-retry'})]) as request:
            self.job._optimize_uploaded_video(self.config)
        self.assertEqual(self.job.optimization_state, 'done')
        self.assertEqual(self.job.playlist_id, 'PLopt1234567890')
        self.assertEqual(self.job.playlist_item_id, 'added-after-retry')
        self.assertFalse(self.job.optimization_next_attempt)
        self.assertFalse(any(call.args[1]=='POST' and call.args[2].endswith('/playlists') for call in request.call_args_list))

    def test_retry_stops_after_four_attempts_and_does_not_repeat_thumbnail(self):
        self.job.thumbnail_applied = True
        self.job.playlist_id = 'PLopt1234567890'
        self.job.optimization_attempts = 3
        with patch.object(type(self.job), '_request', side_effect=[self.channel(), requests.Timeout()]):
            self.job._optimize_uploaded_video(self.config)
        self.assertEqual(self.job.optimization_state, 'failed')
        self.assertEqual(self.job.optimization_attempts, 4)
        self.assertFalse(self.job.optimization_next_attempt)
        self.assertTrue(self.job.thumbnail_applied)
        self.job.action_retry_optimization()
        self.assertEqual(self.job.optimization_attempts, 0)

    def test_http_reason_is_preserved_and_only_transient_errors_retry(self):
        for status, reason, retry in [(404, 'playlistNotFound', True), (403, 'forbidden', False)]:
            with patch.object(type(self.config), '_token', return_value='test-token'), patch(
                    'requests.request', return_value=response(status=status,
                    body={'error': {'errors': [{'reason': reason}]}})):
                try:
                    self.job._request('youtube', 'GET', 'https://www.googleapis.com/youtube/v3/playlistItems')
                except TransferError as exc:
                    self.assertEqual(exc.status, status)
                    self.assertEqual(exc.reason, reason)
                    self.assertEqual(self.job._optimization_retryable(exc), retry)
                else:
                    self.fail('Expected YouTube error')

    def test_cron_does_not_retry_before_scheduled_time(self):
        self.job.optimization_next_attempt = fields.Datetime.add(fields.Datetime.now(), hours=1)
        with patch.object(type(self.config), '_ready'), patch.object(type(self.job), '_request') as request:
            self.config.processing_enabled = True
            self.env['edu.video.job']._cron_optimize()
        request.assert_not_called()

    def test_thumbnail_is_sharp_4k_bounded_for_long_vietnamese_names(self):
        data = render_thumbnail('MS NGUYỄN THỊ MINH ANH ' * 12, 103, '29/10/2026', part=2,
                                students=['Nguyễn Minh Anh', 'Trần Hoàng Bảo Ngọc', 'VeryLongName' * 40])
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.size, (3840, 2160))
            self.assertEqual(image.format, 'JPEG')
        self.assertLess(len(data), 2 * 1024 ** 2)

    def test_generated_cover_uses_same_student_names_as_video_title_and_keeps_cached_image(self):
        self.student.name_en = '  kelly  '
        other = self.env['edu.student'].create({'name_vi': 'Nguyễn Minh Anh'})
        self.session.write({'attendee_ids': [(0, 0, {'student_id': other.id, 'present': False})]})
        with patch('odoo.addons.edu_video.models.optimization.render_thumbnail', return_value=b'cover') as render:
            self.assertEqual(self.job._generated_thumbnail(), b'cover')
            self.assertEqual(render.call_args.kwargs['students'], ['Kelly', 'Nguyễn Minh Anh'])
            self.assertIn('Kelly & Nguyễn Minh Anh', self.job._youtube_title(self.session))
            self.assertEqual(self.job._generated_thumbnail(), b'cover')
            self.assertEqual(render.call_count, 1)

    def test_generated_cover_falls_back_to_extra_participants(self):
        self.session.attendee_ids.unlink()
        self.session.extra_participants = '  alex & lily  '
        with patch('odoo.addons.edu_video.models.optimization.render_thumbnail', return_value=b'cover') as render:
            self.job._generated_thumbnail()
            self.assertEqual(render.call_args.kwargs['students'], ['Alex & Lily'])
