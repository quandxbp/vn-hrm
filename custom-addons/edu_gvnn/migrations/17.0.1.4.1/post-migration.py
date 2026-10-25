import logging
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    count = env['edu.session']._migrate_legacy_recordings()
    logging.getLogger(__name__).info('Moved %s legacy YouTube links into session video fields', count)
