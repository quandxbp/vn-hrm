from odoo import http
from odoo.http import request
from odoo.addons.website_crm.controllers.website_form import WebsiteForm


class LandingForms(http.Controller):
    @http.route('/edu-landing/form-session', type='json', auth='public', methods=['POST'], website=True)
    def form_session(self):
        """Refresh the form's token after login/logout in another browser tab."""
        return {'csrf_token': request.csrf_token(None), 'database': request.db}


class LandingWebsiteForm(WebsiteForm):
    def insert_record(self, request, model, values, custom, meta=None):
        if model.model == 'crm.lead' and request.params.get('edu_registration') == '1':
            values = dict(values, edu_website_registration=True,
                edu_program_interest=request.params.get('Chương trình quan tâm') or False)
            # Internal marker should not clutter the registration notes.
            custom = '\n'.join(line for line in custom.splitlines()
                if not line.startswith('edu_registration :'))
        return super().insert_record(request, model, values, custom, meta=meta)
