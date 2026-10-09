import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.data.database_data import DatabaseData
from app.managers.tv_manager import TVManager
from app.managers.schedule_manager import ScheduleManager
from app.models.schemas import TVConfig

SCHEDULE = {x:[['00:00','23:59']] for x in ('mon','tue','wed','thu','fri','sat','sun')}

class DevicesLocksStatsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = DatabaseData(Path(self.tmp.name)/'local.db')
        self.tvs = TVManager(self.data)
        self.tv = TVConfig('test','Test','192.168.3.123',True,SCHEDULE,120,300).validate()
        self.tvs.save(self.tv)

    def test_migrations_are_idempotent(self):
        self.assertEqual(len(self.data.migration_history()),6)
        DatabaseData(self.data.path)
        self.assertEqual(len(self.data.migration_history()),6)

    def test_lock_overrides_schedule_and_bonus(self):
        mgr=ScheduleManager(self.data)
        now=datetime(2026,10,9,15,tzinfo=timezone.utc)
        mgr.locks.set(self.tv,'indefinite',now)
        result=mgr.evaluate(self.tv,now)
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'],'manual_lock')
        mgr.locks.clear('test')
        self.assertFalse(mgr.evaluate(self.tv,now)['locked'])

    def test_until_tomorrow_expires_at_local_midnight(self):
        mgr=ScheduleManager(self.data)
        now=datetime(2026,10,9,15,tzinfo=timezone.utc)
        lock=mgr.locks.set(self.tv,'until_tomorrow',now)
        self.assertEqual(datetime.fromisoformat(lock['expires_at']).astimezone(__import__('zoneinfo').ZoneInfo('Europe/Berlin')).hour,0)
        self.assertIsNone(mgr.locks.get('test', datetime.fromisoformat(lock['expires_at'])))

    def test_sessions_and_delete(self):
        self.data.start_usage_session('test','2026-10-09T15:00:00+00:00')
        self.data.add_session_duration('test',30)
        self.data.end_usage_session('test','2026-10-09T15:00:30+00:00')
        stats=self.data.usage_statistics('test')
        self.assertEqual(stats['sessions'][0]['duration_seconds'],30)
        self.tvs.delete('test')
        self.assertFalse(self.data.usage_statistics('test')['sessions'])
