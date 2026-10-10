import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from main import SamsungApplication
from app.managers.auth_manager import AuthError
from app.models.schemas import ValidationError

DEFAULT = {'show_tv_count': True, 'show_online_count': True, 'show_blocked_count': True}


class UserPreferencesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.app = SamsungApplication(self.directory)
        self.app.auth.create({'username':'admin', 'display_name':'Admin', 'role':'admin',
                              'credential_type':'pin', 'credential':'12345678'}, bootstrap=True)
        self.app.auth.create({'username':'viewer', 'display_name':'Viewer', 'role':'viewer',
                              'credential_type':'pin', 'credential':'12345678'})
        self.admin = self.app.auth.login({'username':'admin','credential':'12345678'})
        self.viewer = self.app.auth.login({'username':'viewer','credential':'12345678'})
        with patch('app.api.http_api.ThreadingHTTPServer') as server:
            self.app.http.serve()
            self.handler_type = server.call_args.args[1]

    def request(self, session, method='GET', body=None, path='/api/auth/preferences', csrf=None):
        token, expected_csrf, _ = session
        handler = object.__new__(self.handler_type)
        handler.headers = {'X-CSRF-Token': expected_csrf if csrf is None else csrf}
        handler.client_address = ('127.0.0.1', 12345)
        handler.cookie_token = lambda: token
        handler.body_json = lambda: body
        result = []
        handler.reply = lambda value, *args, **kwargs: result.append(value)
        handler.handle_api(method, path, '')
        return result[0]

    def test_viewer_can_save_only_their_own_preferences_and_persist_across_restart(self):
        self.assertEqual(self.request(self.viewer), DEFAULT)
        hidden = {key: False for key in DEFAULT}
        self.assertEqual(self.request(self.viewer, 'PUT', hidden), hidden)
        self.assertEqual(self.request(self.admin), DEFAULT)
        restarted = SamsungApplication(self.directory)
        self.assertEqual(restarted.data.get_user_preferences(self.viewer[2]['id']), hidden)
        self.assertEqual(len(restarted.data.migration_history()), 8)

    def test_rejects_other_user_id_and_non_boolean_values(self):
        for invalid in ({**DEFAULT, 'user_id': self.admin[2]['id']},
                        {**DEFAULT, 'show_tv_count': 'false'}, {}, {'show_tv_count': True}):
            with self.assertRaises(ValidationError):
                self.request(self.viewer, 'PUT', invalid)
        self.assertEqual(self.request(self.viewer), DEFAULT)

    def test_preferences_require_csrf_and_power_still_requires_control(self):
        with self.assertRaises(AuthError):
            self.request(self.viewer, 'PUT', DEFAULT, csrf='wrong')
        self.app.facade.power_sender = Mock(return_value={'ok':True,'sent':True})
        with self.assertRaises(AuthError):
            self.request(self.viewer, 'POST', {}, path='/api/tvs/tv/power')
        self.app.facade.power_sender.assert_not_called()
