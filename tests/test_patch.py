import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from app.data.database_data import DatabaseData
from app.models.schemas import TVConfig
from app.managers.tv_manager import TVManager
from main import SamsungApplication

SCHEDULE = {day:[['12:00','20:00']] for day in ('mon','tue','wed','thu','fri','sat','sun')}

class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)

    def test_migration_idempotent(self):
        path=self.directory/'tv.db'
        db=DatabaseData(path)
        self.assertEqual(len(db.migration_history()),7)
        DatabaseData(path)
        self.assertEqual(len(db.migration_history()),7)

    def test_legacy_database_upgrade_preserves_data(self):
        path=self.directory/'tv.db'
        DatabaseData(path)
        manager=TVManager(DatabaseData(path))
        tv=TVConfig('test','Test','192.168.3.22',True,SCHEDULE,90,300).validate()
        manager.save(tv)
        with sqlite3.connect(path) as conn:
            conn.execute('DROP TABLE app_settings')
            conn.execute('DROP TABLE __EFMigrationsHistory')
            conn.execute('PRAGMA user_version=1')
        upgraded=DatabaseData(path)
        self.assertEqual(len(upgraded.migration_history()),7)
        self.assertEqual(TVManager(upgraded).get('test'),tv)

    def test_json_import_once_and_api_facade(self):
        old={'poll_seconds':8,'tvs':[{'tv_id':'anessa','name':'Anessa TV',
            'ip':'192.168.3.86','enabled':True,'schedule':SCHEDULE,
            'daily_limit_minutes':120,'weekly_limit_minutes':720}]}
        (self.directory/'config.json').write_text(json.dumps(old))
        app=SamsungApplication(self.directory)
        self.assertEqual(app.settings.get()['poll_seconds'],8)
        self.assertEqual(len(app.facade.get_tvs()),1)
        self.assertFalse((self.directory/'config.json').exists())
        self.assertTrue((self.directory/'config.json.imported').exists())
        app2=SamsungApplication(self.directory)
        self.assertEqual(len(app2.facade.get_tvs()),1)
        self.assertEqual(len(app2.data.migration_history()),7)
        settings=app2.settings.get()
        settings.pop('id')
        settings['armed']=False
        self.assertEqual(app2.settings.update(settings)['poll_seconds'],8)
        with self.assertRaises(ValueError):
            app2.settings.update({**settings,'armed':'yes'})
        result=app2.facade.add_bonus('anessa',10,
            (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
        self.assertEqual(result['bonus_remaining_seconds'],600)

if __name__=='__main__':
    unittest.main()
