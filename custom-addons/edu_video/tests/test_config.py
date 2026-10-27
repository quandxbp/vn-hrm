import json
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, AccessError
from ..models.config import CALLBACK, SCOPES, DRIVE_SCOPES, YOUTUBE_SCOPES


@tagged('post_install', '-at_install')
class TestGoogleConnection(TransactionCase):
    def setUp(self):
        super().setUp()
        self.config = self.env.ref('edu_video.config_default')
        self.raw = json.dumps({'web': {'client_id': 'test.apps.googleusercontent.com',
            'client_secret': 'fake-secret', 'redirect_uris': [CALLBACK]}})

    def test_import_and_disconnect(self):
        self.config._import_credentials(self.raw)
        self.assertEqual(self.config.client_id, 'test.apps.googleusercontent.com')
        self.assertEqual(self.config.privacy, 'public')
        self.assertEqual(self.config.audience, 'not_for_kids')
        self.config.sudo().write({'refresh_token': 'fake-refresh', 'state': 'connected'})
        self.config.action_disconnect()
        self.assertFalse(self.config.sudo().refresh_token)
        self.assertEqual(self.config.state, 'disconnected')

    def test_invalid_callback_preserves_credentials(self):
        self.config._import_credentials(self.raw)
        with self.assertRaises(UserError):
            self.config._import_credentials(self.raw.replace(CALLBACK, 'https://example.com/callback'))
        self.assertEqual(self.config.sudo().client_secret, 'fake-secret')

    def test_nonadmin_cannot_import(self):
        with self.assertRaises(AccessError):
            self.config.with_user(self.env.ref('base.public_user'))._import_credentials(self.raw)

    def test_youtube_chooser_does_not_request_drive_scope(self):
        self.config._import_credentials(self.raw)
        request = Mock(session={})
        with patch('odoo.http.request', new=request):
            action = self.config.action_connect()
        params = parse_qs(urlparse(action['url']).query)
        self.assertEqual(set(params['scope'][0].split()), set(YOUTUBE_SCOPES.split()))
        self.assertEqual(params['prompt'], ['select_account consent'])
        self.assertEqual(request.session['edu_video_oauth']['service'], 'youtube')
        with patch('odoo.http.request', new=request):
            action = self.config.action_connect_drive()
        self.assertEqual(parse_qs(urlparse(action['url']).query)['scope'], [DRIVE_SCOPES])

    @patch('odoo.addons.edu_video.models.config.requests.get')
    @patch('odoo.addons.edu_video.models.config.requests.post')
    def test_expected_channel_and_independent_drive_tokens(self, post, get):
        self.config._import_credentials(self.raw)
        self.config.expected_channel_handle = '@YUYONG90'
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'access_token': 'fake-youtube-access',
            'refresh_token': 'fake-youtube-refresh', 'scope': YOUTUBE_SCOPES}
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'items': [{'id': 'wrong-channel',
            'snippet': {'title': 'Personal Channel', 'customUrl': '@other'}}]}
        with self.assertRaises(UserError):
            self.config._exchange('fake-code')
        self.assertFalse(self.config.sudo().youtube_refresh_token)
        get.return_value.json.return_value = {'items': [{'id': 'target-channel',
            'snippet': {'title': 'AU KIM NGAN', 'customUrl': '@yuyong90'}}]}
        self.config._exchange('fake-code')
        self.assertEqual(self.config.channel_id, 'target-channel')
        post.return_value.json.return_value = {'access_token': 'fake-drive-access',
            'refresh_token': 'fake-drive-refresh', 'scope': DRIVE_SCOPES}
        get.reset_mock()
        self.config._exchange('fake-code', service='drive')
        get.assert_not_called()
        self.assertEqual(self.config.sudo().refresh_token, 'fake-drive-refresh')
        self.assertEqual(self.config.sudo().youtube_refresh_token, 'fake-youtube-refresh')
        self.assertEqual(self.config.channel_id, 'target-channel')

    @patch('odoo.addons.edu_video.models.config.requests.get')
    @patch('odoo.addons.edu_video.models.config.requests.post')
    def test_exchange_verifies_channel_and_permissions(self, post, get):
        self.config.expected_channel_handle = False
        self.config._import_credentials(self.raw)
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'access_token': 'fake-access',
            'refresh_token': 'fake-refresh', 'scope': SCOPES, 'expires_in': 3600}
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'items': [{'id': 'channel-test',
            'snippet': {'title': 'Test Channel'}}]}
        self.config._exchange('fake-code')
        self.assertEqual(self.config.channel_id, 'channel-test')
        self.assertEqual(self.config.state, 'connected')
        self.config.action_disconnect()
        post.return_value.json.return_value['scope'] = 'https://www.googleapis.com/auth/youtube.upload'
        with self.assertRaises(UserError):
            self.config._exchange('fake-code')
        self.assertEqual(self.config.state, 'disconnected')
