"""Regression: schedule permission must not generate usage for an offline TV."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.data.database_data import DatabaseData
from app.managers.automation_manager import AutomationManager
from app.managers.schedule_manager import ScheduleManager
from app.managers.tv_manager import TVManager
from app.models.schemas import RuntimeConfig, TVConfig
from app.services.samsung_service import SamsungService
from app.api.handlers import TVApi

DAYS=('mon','tue','wed','thu','fri','sat','sun')
SCHEDULE={day:[['00:00','23:59']] for day in DAYS}

class MockSamsung:
    online=False
    def is_reachable(self, tv):
        return self.online
    def power_hold(self, tv, seconds):
        raise AssertionError('TV should not be powered')

class UsageDetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data=DatabaseData(Path(self.tmp.name)/'db.sqlite')
        self.tvs=TVManager(self.data)
        self.tv=TVConfig('test','Test','192.168.3.86',True,SCHEDULE,120,720).validate()
        self.tvs.save(self.tv)
        self.schedule=ScheduleManager(self.data)
        self.samsung=MockSamsung()
        self.engine=AutomationManager(self.tvs,self.schedule,self.data,self.samsung,RuntimeConfig(),False)
        self.start=datetime(2026,10,9,12,0,tzinfo=timezone.utc)

    def step(self, offset):
        self.engine.tick(self.start+timedelta(seconds=offset), 100+offset)

    def test_offline_does_not_accumulate_even_when_schedule_allows(self):
        for t in range(0,180,5):
            self.step(t)
        status=self.schedule.evaluate(self.tv,self.start+timedelta(seconds=180))
        self.assertTrue(status['allowed'])
        self.assertEqual(status['used_today_seconds'],0)
        self.assertEqual(status['used_week_seconds'],0)

    def test_usage_stops_on_offline_and_keeps_historical_count(self):
        self.samsung.online=True
        for t in range(0,30,5):
            self.step(t)
        before=self.schedule.evaluate(self.tv,self.start+timedelta(seconds=30))['used_today_seconds']
        self.assertGreater(before,0)
        self.samsung.online=False
        for t in range(30,180,5):
            self.step(t)
        after=self.schedule.evaluate(self.tv,self.start+timedelta(seconds=180))['used_today_seconds']
        self.assertEqual(after,before)
        facade=TVApi(self.tvs,self.schedule,self.data,lambda tv_id: {
            'state':'offline','reachable':False,'confirmed_online':False,
            'last_checked_at':self.start.isoformat()})
        status=facade.get_status('test')
        self.assertEqual(status['online_observation']['state'],'offline')
        self.assertTrue(status['usage_is_estimate'])

    def test_requires_both_ports(self):
        seen=[]
        class SocketContext:
            def __enter__(self): return self
            def __exit__(self,*a): return False
        def connect(addr,timeout):
            seen.append(addr[1])
            if addr[1]==9197:
                raise ConnectionRefusedError('closed')
            return SocketContext()
        svc=SamsungService(Path(self.tmp.name)/'tokens')
        with patch('app.services.samsung_service.socket.create_connection',side_effect=connect):
            self.assertFalse(svc.is_reachable(self.tv))
        self.assertEqual(seen,[8002,9197])

if __name__=='__main__':
    unittest.main()
