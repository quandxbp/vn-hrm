import re

from odoo import api, fields, models
from odoo.tools import html2plaintext


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    edu_website_registration = fields.Boolean('Đăng ký từ website', index=True, copy=False)
    edu_program_interest = fields.Char('Chương trình quan tâm', tracking=True)

    @api.model
    def _migrate_website_registrations(self):
        """Include existing consultation requests without changing their CRM type."""
        registrations = self.with_context(active_test=False).search([
            ('edu_website_registration', '=', False),
            ('name', '=', 'Đăng ký tư vấn từ website'),
            ('description', 'ilike', 'Chương trình quan tâm'),
        ])
        for registration in registrations:
            description = html2plaintext(registration.description or '')
            match = re.search(r'Chương trình quan tâm\s*:\s*([^\r\n]+)', description)
            if match:
                registration.with_context(tracking_disable=True).write({
                    'edu_website_registration': True,
                    'edu_program_interest': match.group(1).strip(),
                })
