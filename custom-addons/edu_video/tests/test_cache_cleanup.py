import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from ..models.job import LOCK_NAMESPACE, TransferError


@tagged('post_install', '-at_install')
class TestVideoCacheCleanup(TransactionCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = patch('odoo.addons.edu_video.models.job.server_config', {'data_dir': self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.Job = self.env['edu.video.job']
        checkpoint = patch.object(type(self.Job), '_checkpoint')
        checkpoint.start()
        self.addCleanup(checkpoint.stop)
        teacher = self.env['edu.teacher'].create({'name': 'Video Retention Test Teacher'})
        session = self.env['edu.session'].create({'date': '2050-01-02', 'teacher_id': teacher.id})
        self.job = self.Job.create({'session_id': session.id,
            'source_url': 'https://drive.google.com/file/d/retention_file_12345/view',
            'file_id': 'retention_file_12345'})
        self.old = fields.Datetime.now() - timedelta(days=8)

    def cache(self):
        path = self.job._path()
        path.write_bytes(b'fake cached video')
        return path

    def test_expires_by_start_time_even_when_file_was_updated_recently(self):
        path = self.cache()
        self.job.write({'state': 'downloading', 'cache_started_at': self.old})
        self.assertEqual(self.Job._cron_cleanup_video_cache(), 1)
        self.assertFalse(path.exists())
        self.assertEqual(self.job.state, 'cancelled')
        self.assertTrue(self.job.cache_expired)
        self.assertIn('7', self.job.error)
        self.assertEqual(self.Job._cron_cleanup_video_cache(), 0)

    def test_recent_file_is_kept_and_cleanup_does_not_need_google_connection(self):
        path = self.cache()
        self.job.write({'state': 'failed', 'cache_started_at': fields.Datetime.now()})
        with patch.object(type(self.Job), '_request') as request:
            self.assertEqual(self.Job._cron_cleanup_video_cache(), 0)
            request.assert_not_called()
        self.assertTrue(path.exists())
        self.assertEqual(self.job.state, 'failed')

    def test_expired_upload_requires_remote_check_before_retry(self):
        path = self.cache()
        self.job.write({'state': 'uploading', 'cache_started_at': self.old,
                        'upload_url': 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=fake'})
        self.Job._cron_cleanup_video_cache()
        self.assertFalse(path.exists())
        self.assertEqual(self.job.state, 'uncertain')
        self.assertTrue(self.job.upload_url)
        with self.assertRaises(UserError):
            self.job.action_retry()
        self.job.action_restart_checked()
        self.assertFalse(self.job.cache_expired)
        self.assertFalse(self.job.cache_started_at)
        self.assertFalse(self.job.upload_url)
        self.assertEqual(self.job.state, 'queued')

    def test_retry_after_expired_download_starts_a_fresh_retention_period(self):
        self.cache()
        self.job.write({'state': 'downloading', 'cache_started_at': self.old})
        self.Job._cron_cleanup_video_cache()
        self.job.action_retry()
        self.assertEqual(self.job.state, 'queued')
        self.assertFalse(self.job.cache_expired)
        self.assertFalse(self.job.cache_started_at)

    def test_legacy_and_orphan_files_expire_without_touching_other_files(self):
        path = self.cache()
        self.env.cr.execute('UPDATE edu_video_job SET create_date=%s WHERE id=%s', [self.old, self.job.id])
        self.job.invalidate_recordset()
        orphan = path.parent / '2147483000.video'
        orphan.write_bytes(b'orphan')
        old_epoch = self.old.timestamp()
        os.utime(orphan, (old_epoch, old_epoch))
        other = path.parent / 'keep.mp4'
        other.write_bytes(b'unrelated')
        sibling = path.parent.parent / 'other_database'
        sibling.mkdir()
        sibling_file = sibling / '123.video'
        sibling_file.write_bytes(b'other database')
        self.assertEqual(self.Job._cron_cleanup_video_cache(), 2)
        self.assertFalse(path.exists())
        self.assertFalse(orphan.exists())
        self.assertTrue(other.exists())
        self.assertTrue(sibling_file.exists())

    def test_busy_worker_file_is_not_deleted(self):
        path = self.cache()
        self.job.cache_started_at = self.old
        with self.registry.cursor() as worker:
            worker.execute('SELECT pg_advisory_lock(%s, %s)', [LOCK_NAMESPACE, self.job.id])
            try:
                self.assertEqual(self.Job._cron_cleanup_video_cache(), 0)
                self.assertTrue(path.exists())
                self.assertFalse(self.job.cache_expired)
            finally:
                worker.execute('SELECT pg_advisory_unlock(%s, %s)', [LOCK_NAMESPACE, self.job.id])
        self.assertEqual(self.Job._cron_cleanup_video_cache(), 1)

    def test_symlinks_are_not_followed(self):
        folder = self.job._path().parent
        outside = Path(self.tmp.name) / 'outside.video'
        outside.write_bytes(b'do not delete')
        (folder / '2147483000.video').symlink_to(outside)
        self.assertEqual(self.Job._cron_cleanup_video_cache(), 0)
        self.assertTrue(outside.exists())

    def test_done_state_and_video_links_are_preserved(self):
        self.cache()
        self.job.write({'state': 'done', 'cache_started_at': self.old, 'video_url': 'https://youtu.be/keepvideo12'})
        self.Job._cron_cleanup_video_cache()
        self.assertEqual(self.job.state, 'done')
        self.assertEqual(self.job.video_url, 'https://youtu.be/keepvideo12')

    def test_worker_refuses_expired_cache_before_calling_google(self):
        self.job.cache_started_at = self.old
        with patch.object(type(self.Job), '_request') as request:
            with self.assertRaises(TransferError):
                self.job._guard()
            request.assert_not_called()

    def test_cleanup_cron_is_enabled_independently(self):
        cron = self.env.ref('edu_video.cron_cleanup_video_cache')
        self.assertTrue(cron.active)
        self.assertEqual((cron.interval_number, cron.interval_type), (15, 'minutes'))

    def test_failed_unlink_does_not_restart_expired_work_or_reset_its_age(self):
        path = self.cache()
        self.job.write({'state': 'failed', 'cache_started_at': self.old})
        with patch.object(Path, 'unlink', side_effect=PermissionError('test permission error')):
            # Also protect the interval after expiry but before the sweep marks the job.
            with self.assertRaises(UserError):
                self.job.action_retry()
            with self.assertRaises(UserError):
                self.job.action_restart_checked()
            self.assertEqual(self.Job._cron_cleanup_video_cache(), 0)
            self.assertTrue(path.exists())
            self.assertEqual(self.job.state, 'cancelled')
            with self.assertRaises(UserError):
                self.job.action_retry()
            self.assertTrue(self.job.cache_expired)
            self.assertEqual(self.job.cache_started_at, self.old)
        self.assertEqual(self.Job._cron_cleanup_video_cache(), 1)
        self.assertFalse(path.exists())

    def test_cache_directory_symlink_is_not_followed(self):
        folder = self.Job._cache_folder()
        folder.parent.mkdir(parents=True)
        outside = Path(self.tmp.name) / 'outside-cache'
        outside.mkdir()
        file = outside / '2147483000.video'
        file.write_bytes(b'keep outside directory')
        folder.symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.Job._cron_cleanup_video_cache(), 0)
        self.assertTrue(file.exists())
