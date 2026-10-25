from odoo.tests import TransactionCase, tagged
from ..tools import youtube_recording_url


@tagged('post_install', '-at_install')
class TestLegacyVideo(TransactionCase):
    def setUp(self):
        super().setUp()
        self.teacher = self.env['edu.teacher'].create({'name': 'Legacy Video Test Teacher'})

    def session(self, **values):
        return self.env['edu.session'].create({'date': '2035-04-03',
            'teacher_id': self.teacher.id, **values})

    def test_migration_preserves_data_and_does_not_overwrite_existing_link(self):
        old = self.session(recording_url='https://youtu.be/oldvideo123', video_posted=True)
        old.write({'paid': True})
        existing = self.session(recording_url='https://youtu.be/oldvideo123', youtube_url='https://youtu.be/newvideo123')
        other = self.session(recording_url='https://example.com/recording')
        self.env.flush_all()
        self.env['edu.session']._migrate_legacy_recordings()
        self.assertEqual(old.youtube_url, old.recording_url)
        self.assertTrue(old.paid)
        self.assertTrue(old.video_posted)
        self.assertEqual(existing.youtube_url, 'https://youtu.be/newvideo123')
        self.assertFalse(other.youtube_url)
        self.assertEqual(self.env['edu.session']._migrate_legacy_recordings(), 0)

    def test_export_uses_current_video_fields_and_legacy_fallback(self):
        export = self.env['edu.export.week.wizard']
        current = self.session(youtube_url='https://youtu.be/newvideo123', recording_url='https://youtu.be/oldvideo123')
        drive = self.session(google_drive_url='https://drive.google.com/file/d/test_file_123456/view')
        old = self.session(recording_url='https://example.com/old', video_posted=True)
        self.assertEqual(export._video_values(current), ('https://youtu.be/newvideo123', 'OK'))
        self.assertEqual(export._video_values(drive), (drive.google_drive_url, ''))
        self.assertEqual(export._video_values(old), (old.recording_url, 'OK'))

    def test_recording_host_matching(self):
        self.assertEqual(youtube_recording_url(' https://www.youtube.com/watch?v=oldvideo123 '),
                         'https://www.youtube.com/watch?v=oldvideo123')
        self.assertFalse(youtube_recording_url('https://youtube.com.example.org/watch?v=oldvideo123'))
        self.assertFalse(youtube_recording_url('https://drive.google.com/file/d/test_file_123456/view'))
