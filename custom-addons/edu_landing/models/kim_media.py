"""Install the curated Facebook photos once without replacing editorial uploads."""
import base64
import hashlib

from odoo import api, models
from odoo.tools import file_open, image_process


class WebsiteKimMedia(models.Model):
    _inherit = 'website'

    @api.model
    def _install_kim_photos(self):
        params = self.env['ir.config_parameter'].sudo()
        marker = 'edu_landing.kim_photos_20261025'
        if params.get_param(marker):
            return

        def photo(name):
            with file_open('edu_landing/static/src/img/' + name, 'rb') as stream:
                return stream.read()

        # Compare the actual bytes as well as Odoo's resized form. A renamed sample
        # is still a sample; a user-uploaded replacement must never be hidden.
        def retire_samples(model, paths):
            hashes = set()
            for path in paths:
                raw = photo(path)
                for version in (raw, image_process(raw, size=(1920, 1920))):
                    hashes.add(hashlib.sha256(version).digest())
            for record in self.env[model].search([('is_published', '=', True)]):
                if record.image_1920 and hashlib.sha256(base64.b64decode(record.image_1920)).digest() in hashes:
                    record.is_published = False

        retire_samples('edu.landing.teacher', ['teacher_%s.jpg' % i for i in range(1, 5)])
        retire_samples('edu.landing.student', ['student_%s.jpg' % i for i in range(1, 5)])
        retire_samples('edu.landing.activity', ['activities/%s.jpg' % name for name in
                                             ('classroom', 'creative', 'learning', 'teamwork')])

        # These are documentary cards, with no invented names, titles or exam scores.
        for title, filename, position in [
            ('Tận tâm với từng bài học', 'teacher-desk', 'Đồng hành cùng học viên'),
            ('Đội ngũ Kim Academy', 'team-celebration', 'Gắn kết và sẻ chia'),
        ]:
            self.env['edu.landing.teacher'].create({
                'name': title, 'position': position, 'team': 'center',
                'alt_text': title + ' — ảnh từ Facebook Kim Academy',
                'image_1920': base64.b64encode(photo('kim/' + filename + '.jpg')),
                'is_published': True,
            })
        for title, filename, description in [
            ('Vinh danh học viên Cambridge', 'recognition', 'Khoảnh khắc nhận chứng chỉ cùng Kim Academy.'),
            ('Niềm vui nhận chứng chỉ', 'student-awards', 'Ghi nhận những bước tiến trên hành trình học tiếng Anh.'),
        ]:
            self.env['edu.landing.student'].create({
                'name': title, 'category': 'cambridge', 'description': description,
                'alt_text': title + ' tại Kim Academy',
                'image_1920': base64.b64encode(photo('kim/' + filename + '.jpg')),
                'is_published': True,
            })
        event = self.env['edu.landing.activity.event'].create({
            'name': 'Khoảnh khắc Kim Academy',
            'description': 'Ảnh tuyển chọn từ facebook.com/mskim.kimacademy/photos, ngày 25/10/2026. '
                           'Các ảnh thuộc nhiều bài đăng; không gán cùng ngày diễn ra.',
        })
        for index, (filename, title) in enumerate([
            ('classroom-boards', 'Cùng luyện tập trong lớp học'),
            ('classroom-speaking', 'Tự tin thực hành tiếng Anh'),
            ('classroom-learning', 'Tập trung trong từng bài học'),
            ('recognition', 'Niềm vui nhận chứng chỉ Cambridge'),
            ('community', 'Kết nối cùng Kim Academy'),
            ('study-together', 'Cùng đọc sách và trao đổi học tập'),
        ], start=1):
            self.env['edu.landing.activity'].create({
                'event_id': event.id, 'name': title, 'alt_text': title,
                'sequence': index * 10, 'is_published': True,
                'image_1920': base64.b64encode(photo('kim/' + filename + '.jpg')),
            })
        for suffix, old, new in [
            ('kinder', 'prog_kinder', 'learning-materials'),
            ('primary', 'prog_primary', 'classroom-boards'),
            ('teen', 'prog_teen', 'classroom-speaking'),
            ('ielts_sat', 'prog_ielts', 'study-together'),
        ]:
            course = self.env.ref('edu_landing.course_' + suffix, raise_if_not_found=False)
            if course and course.fallback_image == '/edu_landing/static/src/img/' + old + '.jpg':
                course.fallback_image = '/edu_landing/static/src/img/kim/' + new + '.jpg'
        params.set_param(marker, '1')
