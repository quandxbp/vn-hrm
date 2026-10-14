from odoo import http
from odoo.http import request


class LandingCourses(http.Controller):
    @http.route('/khoa-hoc/<string:slug>', type='http', auth='public', website=True, sitemap=False)
    def course_detail(self, slug, **kwargs):
        course = request.env['edu.landing.course'].search([
            ('slug', '=', slug), ('is_published', '=', True),
            '|', ('website_id', '=', False), ('website_id', '=', request.website.id),
        ], limit=1)
        if not course:
            return request.not_found()
        # Only the default asset path needs elevated access; course content obeys public rules.
        default_image = course.sudo().fallback_image or '/edu_landing/static/src/img/prog_primary.jpg'
        return request.render('edu_landing.course_detail', {
            'course': course, 'default_image': default_image,
        })
