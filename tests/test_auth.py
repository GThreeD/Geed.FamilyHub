import tempfile
import unittest
from pathlib import Path
from app.data.database_data import DatabaseData
from app.managers.auth_manager import AuthManager, AuthError

class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=DatabaseData(Path(self.tmp.name)/'test.db')
        self.auth=AuthManager(self.db)
        self.admin={'username':'owner','display_name':'Owner','role':'viewer','credential_type':'pin','credential':'12345678'}

    def test_first_user_is_admin_and_setup_is_unique(self):
        user=self.auth.create(self.admin,bootstrap=True)
        self.assertEqual(user['role'],'admin')
        with self.assertRaises(AuthError):self.auth.create(self.admin,bootstrap=True)
        self.assertEqual(self.db.user_count(),1)
        self.assertNotIn('secret_hash',str(self.db.list_users()))

    def test_pin_login_role_csrf_logout(self):
        self.auth.create(self.admin,bootstrap=True)
        token,csrf,user=self.auth.login({'username':'owner','credential':'12345678'})
        active=self.auth.current(token)
        self.assertEqual(user['role'],'admin')
        self.auth.require(active,'users')
        self.auth.verify_csrf(active,csrf)
        with self.assertRaises(AuthError):self.auth.verify_csrf(active,'bad')
        csrf2=self.auth.new_csrf(token)
        self.auth.verify_csrf(self.auth.current(token),csrf2)
        self.auth.logout(token)
        with self.assertRaises(AuthError):self.auth.current(token)

    def test_lockout_and_role_restrictions(self):
        self.auth.create(self.admin,bootstrap=True)
        self.auth.create({'username':'guest','display_name':'Guest','role':'viewer','credential_type':'pattern','credential':'1235789'})
        with self.assertRaises(AuthError):self.auth.require({'role':'viewer'},'config')
        token,csrf,user=self.auth.login({'username':'guest','credential':'1235789'})
        self.assertEqual(user['role'],'viewer')
        for _ in range(5):
            with self.assertRaises(AuthError):self.auth.login({'username':'owner','credential':'wrong'})
        with self.assertRaises(AuthError) as ctx:
            self.auth.login({'username':'owner','credential':'12345678'})
        self.assertEqual(ctx.exception.status,429)

    def test_admin_cannot_disable_only_admin(self):
        uid=self.auth.create(self.admin,bootstrap=True)['id']
        with self.assertRaises(ValueError):self.db.modify_user(uid,active=False)
        self.assertTrue(self.db.user_by_id(uid)['active'])

if __name__=='__main__':unittest.main()
