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
from app.services.samsung_service import SamsungService, PowerObservation
from unittest.mock import Mock, call
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

    def test_slow_network_polls_still_count_actual_online_duration(self):
        self.samsung.online = True
        for offset in (0, 10, 20, 30, 40):
            self.step(offset)
        self.assertEqual(self.schedule.evaluate(self.tv, self.start)['used_today_seconds'], 20)

    def test_restart_resumes_saved_52_minutes_without_backfilling_downtime(self):
        self.data.record_usage(self.tv.tv_id, '2026-10-09', '2026-W41', 52*60, 0, self.start.isoformat())
        self.data.start_usage_session(self.tv.tv_id, self.start.isoformat())
        # Reload persistence and discard in-memory observations as an update does.
        self.data = DatabaseData(self.data.path)
        self.tvs = TVManager(self.data)
        self.schedule = ScheduleManager(self.data)
        self.samsung.online = True
        self.engine = AutomationManager(self.tvs, self.schedule, self.data, self.samsung, RuntimeConfig(), False)
        for offset in (600, 610, 620):
            self.step(offset)
        self.assertEqual(self.schedule.evaluate(self.tv, self.start)['used_today_seconds'], 52*60)
        self.step(630)
        self.step(640)
        self.assertEqual(self.schedule.evaluate(self.tv, self.start)['used_today_seconds'], 52*60+20)
        self.assertEqual(self.data.usage_statistics(self.tv.tv_id)['sessions'][0]['duration_seconds'], 20)

    def test_subsecond_poll_time_accumulates_without_rounding_loss(self):
        self.samsung.online = True
        for offset in (0, 5.5, 11, 16.5, 22):
            self.step(offset)
        self.assertEqual(self.schedule.evaluate(self.tv, self.start)['used_today_seconds'], 11)

    def test_long_unobserved_pause_is_not_backfilled_but_counting_recovers(self):
        self.samsung.online = True
        for offset in (0, 5, 10, 15, 600, 605):
            self.step(offset)
        self.assertEqual(self.schedule.evaluate(self.tv, self.start)['used_today_seconds'], 10)

    def test_unknown_sample_does_not_count_as_contiguous_online_time(self):
        samsung = Mock()
        samsung.observe_power.return_value = PowerObservation('on', 'api')
        self.engine = AutomationManager(self.tvs, self.schedule, self.data, samsung, RuntimeConfig(), False)
        for offset in (0, 5, 10):
            self.step(offset)
        samsung.observe_power.return_value = PowerObservation('unknown', 'network')
        self.step(15)
        samsung.observe_power.return_value = PowerObservation('on', 'api')
        self.step(20)
        self.step(25)
        self.assertEqual(self.schedule.evaluate(self.tv, self.start)['used_today_seconds'], 5)

    def test_60_second_poll_with_network_overhead_counts_full_interval(self):
        self.samsung.online = True
        self.engine = AutomationManager(self.tvs, self.schedule, self.data, self.samsung,
                                        RuntimeConfig(poll_seconds=60), False)
        for offset in (0, 62, 124, 186):
            self.step(offset)
        self.assertEqual(self.schedule.evaluate(self.tv, self.start)['used_today_seconds'], 62)

    def test_monitor_wait_subtracts_network_scan_duration(self):
        from main import SamsungApplication
        app = SamsungApplication(Path(self.tmp.name) / 'monitor')
        app._engine = Mock()
        app.stop_event = Mock()
        app.stop_event.is_set.side_effect = [False, False, True]
        # First scan takes 2s of a 5s cycle; the second takes longer than 5s.
        with patch('main.time.monotonic', side_effect=[0, 2, 5, 12]):
            app.monitor()
        self.assertEqual(app.stop_event.wait.call_args_list, [call(3), call(0)])
        self.assertEqual(app._engine.tick.call_count, 2)

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
