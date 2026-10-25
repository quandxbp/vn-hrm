import time
from unittest.mock import Mock, patch

from odoo.tests import TransactionCase, tagged
from odoo.http import Response
from ..controllers import oauth


@tagged('post_install', '-at_install')
class TestGoogleCallback(TransactionCase):
    def test_denial_does_not_exchange_and_does_not_echo_input(self):
        request = Mock()
        request.env = self.env
        request.session = {'edu_video_oauth': {
            'state': 'fake-state', 'uid': self.env.uid, 'db': self.env.cr.dbname,
            'config': self.env.ref('edu_video.config_default').id,
            'expires': time.time() + 600}}
        request.make_response = Mock(return_value=Response(status=400))
        with patch.object(oauth, 'request', new=request):
            oauth.GoogleVideoOAuth().callback(state='fake-state', error='access_denied')
        message = request.make_response.call_args.args[0]
        self.assertIn('access_denied', message)
        self.assertIn('Test users', message)
        self.assertNotIn('edu_video_oauth', request.session)
        self.assertEqual(request.make_response.call_args.kwargs['status'], 400)
        self.assertIn(('Content-Type', 'text/plain; charset=utf-8'),
                      request.make_response.call_args.kwargs['headers'])

    def test_invalid_state_is_rejected_first(self):
        request = Mock()
        request.make_response = Mock(return_value=Response(status=400))
        request.env = self.env
        request.session = {'edu_video_oauth': {
            'state': 'expected', 'uid': self.env.uid, 'db': self.env.cr.dbname,
            'expires': time.time() + 600}}
        with patch.object(oauth, 'request', new=request):
            oauth.GoogleVideoOAuth().callback(state='wrong', error='access_denied')
        self.assertNotIn('Test users', request.make_response.call_args.args[0])
