import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.data.database_data import DatabaseData
from app.models.schemas import TVConfig
from app.managers.tv_manager import TVManager
from app.services.update_service import UpdateService


class BonusUpdateTests(unittest.TestCase):
    def test_bonus_list_and_revoke(self):
        with tempfile.TemporaryDirectory() as directory:
            db = DatabaseData(Path(directory) / 'private' / 'db.sqlite')
            tv = TVConfig('living', 'Wohnzimmer', '192.168.1.21', True, {day: [] for day in ('mon','tue','wed','thu','fri','sat','sun')}, None, None).validate()
            TVManager(db).save(tv)
            now = datetime.now(timezone.utc)
            db.grant_bonus('living', 1800, (now+timedelta(hours=2)).isoformat(), now.isoformat())
            grants = db.list_bonus_grants('living')
            self.assertEqual(len(grants),1)
            self.assertEqual(grants[0]['granted_seconds'],1800)
            self.assertTrue(db.revoke_bonus_grant('living', grants[0]['id']))
            self.assertEqual(db.available_bonus('living',now.isoformat()),0)
            self.assertFalse(db.revoke_bonus_grant('living', grants[0]['id']))

    def test_update_requires_prepared_release(self):
        with tempfile.TemporaryDirectory() as directory:
            service = UpdateService(Path(directory))
            with self.assertRaises(Exception):
                service.install()

if __name__ == '__main__':
    unittest.main()
