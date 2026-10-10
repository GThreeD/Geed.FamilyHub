import tempfile
import unittest
from unittest.mock import Mock
from app.services.samsung_service import PowerObservation
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.data.database_data import DatabaseData
from app.models.schemas import TVConfig, ValidationError, RuntimeConfig
from app.managers.tv_manager import TVManager
from app.managers.schedule_manager import ScheduleManager
from app.managers.automation_manager import AutomationManager

SCHEDULE={d:[['10:00','20:00']] for d in ('mon','tue','wed','thu','fri','sat','sun')}

class FakeSamsung:
    def __init__(self):
        self.online=True
        self.calls=0
    def is_reachable(self,tv):
        return self.online
    def power_hold(self,tv,seconds):
        self.calls+=1

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data=DatabaseData(Path(self.temp.name)/'private'/'app.db')
        self.tvs=TVManager(self.data)
        self.sched=ScheduleManager(self.data)
        self.tv=TVConfig('anessa','Anessa','192.168.3.86',True,SCHEDULE,30,100).validate()
        self.tvs.save(self.tv)
        self.now=datetime(2026,10,9,19,0,tzinfo=timezone.utc)  # 21:00 Berlin, outside window

    def test_validation(self):
        with self.assertRaises(ValidationError):
            TVConfig('x','TV','127.0.0.1',True,SCHEDULE,None,None).validate()
        with self.assertRaises(ValidationError):
            TVConfig('x','TV','192.168.3.22',True,{'mon':[['20:00','19:00']]},None,None).validate()

    def test_bonus_and_quota(self):
        result=self.sched.evaluate(self.tv,self.now)
        self.assertFalse(result['allowed'])
        self.sched.add_bonus('anessa',10,now=self.now)
        result=self.sched.evaluate(self.tv,self.now)
        self.assertGreater(result['bonus_remaining_seconds'],0)
        self.sched.add_usage(self.tv,5,self.now,'bonus')
        total=self.data.usage_totals('anessa','2026-10-09','2026-W41')
        self.assertEqual(total['day'],5)
        self.assertEqual(total['week'],5)

    def test_automation_single_toggle_per_phase(self):
        fake=FakeSamsung()
        engine=AutomationManager(self.tvs,self.sched,self.data,fake,RuntimeConfig(),armed=True)
        for i in range(5):
            engine.tick(self.now+timedelta(seconds=i*5),100+i*5)
        self.assertEqual(fake.calls,1)
        fake.online=False
        for i in range(3):
            engine.tick(self.now+timedelta(seconds=25+i*5),125+i*5)
        fake.online=True
        for i in range(4):
            engine.tick(self.now+timedelta(seconds=50+i*5),150+i*5)
        self.assertEqual(fake.calls,2) # a verified OFF cycle permits a new ON cycle
        future=self.now+timedelta(seconds=200)
        fake.online=False
        for i in range(3):
            engine.tick(future+timedelta(seconds=i*5),300+i*5)
        fake.online=True
        for i in range(3):
            engine.tick(future+timedelta(seconds=15+i*5),315+i*5)
        self.assertEqual(fake.calls,3)

    def test_last_bonus_seconds_do_not_prevent_shutdown(self):
        fake = FakeSamsung()
        engine = AutomationManager(self.tvs, self.sched, self.data, fake, RuntimeConfig(), armed=True)
        self.data.grant_bonus(self.tv.tv_id, 13, (self.now + timedelta(hours=1)).isoformat(), self.now.isoformat())
        for i in range(6):
            engine.tick(self.now + timedelta(seconds=i*5), 100+i*5)
        self.assertEqual(self.data.available_bonus(self.tv.tv_id, self.now.isoformat()), 0)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(self.sched.evaluate(self.tv, self.now)['used_today_seconds'], 15)

    def test_revoking_bonus_enforces_online_device(self):
        fake = FakeSamsung()
        engine = AutomationManager(self.tvs, self.sched, self.data, fake, RuntimeConfig(), armed=True)
        self.data.grant_bonus(self.tv.tv_id, 600, (self.now + timedelta(hours=1)).isoformat(), self.now.isoformat())
        for i in range(3):
            engine.tick(self.now + timedelta(seconds=i*5), 100+i*5)
        self.assertEqual(fake.calls, 0)
        grant = self.data.list_bonus_grants(self.tv.tv_id)[0]
        self.data.revoke_bonus_grant(self.tv.tv_id, grant['id'])
        engine.tick(self.now + timedelta(seconds=15), 115)
        self.assertEqual(fake.calls, 1)

    def test_retry_after_15_seconds_despite_default_120_second_cooldown(self):
        fake = FakeSamsung()
        engine = AutomationManager(self.tvs, self.sched, self.data, fake,
                                   RuntimeConfig(confirm_online_checks=1), armed=True)
        for offset, expected in ((0,1), (5,1), (14,1), (15,2), (20,2), (30,3)):
            engine.tick(self.now + timedelta(seconds=offset), 100+offset)
            self.assertEqual(fake.calls, expected, offset)

    def test_old_power_guard_does_not_block_after_bonus_revocation(self):
        fake = FakeSamsung()
        engine = AutomationManager(self.tvs, self.sched, self.data, fake,
                                   RuntimeConfig(confirm_online_checks=1), armed=True)
        engine.tick(self.now, 100)
        self.assertEqual(fake.calls, 1)
        self.sched.add_bonus(self.tv.tv_id, 10, now=self.now)
        # TV stays ON or is switched back ON without observed standby in between.
        for offset in (5, 10, 15, 20):
            engine.tick(self.now + timedelta(seconds=offset), 100+offset)
        self.assertEqual(fake.calls, 1)
        grant = self.data.list_bonus_grants(self.tv.tv_id)[0]
        self.data.revoke_bonus_grant(self.tv.tv_id, grant['id'])
        engine.tick(self.now + timedelta(seconds=25), 125)
        self.assertEqual(fake.calls, 2)

    def test_no_retry_when_offline_unknown_or_allowed(self):
        fake = Mock()
        fake.observe_power.return_value = PowerObservation('on', 'api')
        engine = AutomationManager(self.tvs, self.sched, self.data, fake,
                                   RuntimeConfig(confirm_online_checks=1), armed=True)
        engine.tick(self.now, 100)
        fake.power_hold.assert_called_once()
        for offset, state in ((15,'unknown'), (20,'standby'), (25,'off')):
            fake.observe_power.return_value = PowerObservation(state, 'api')
            engine.tick(self.now + timedelta(seconds=offset), 100+offset)
        self.sched.add_bonus(self.tv.tv_id, 10, now=self.now)
        fake.observe_power.return_value = PowerObservation('on', 'api')
        engine.tick(self.now + timedelta(seconds=30), 130)
        fake.power_hold.assert_called_once()

    def test_retry_rechecks_on_immediately_before_sending(self):
        fake = Mock()
        fake.observe_power.return_value = PowerObservation('on', 'api')
        engine = AutomationManager(self.tvs, self.sched, self.data, fake,
                                   RuntimeConfig(confirm_online_checks=1), armed=True)
        engine.tick(self.now, 100)
        fake.observe_power.side_effect = [PowerObservation('on', 'api'), PowerObservation('standby', 'api')]
        engine.tick(self.now + timedelta(seconds=15), 115)
        fake.power_hold.assert_called_once()

    def test_shorter_configured_cooldown_remains_effective(self):
        fake = FakeSamsung()
        engine = AutomationManager(self.tvs, self.sched, self.data, fake,
                                   RuntimeConfig(confirm_online_checks=1, cooldown_seconds=5), armed=True)
        engine.tick(self.now, 100)
        engine.tick(self.now + timedelta(seconds=4), 104)
        self.assertEqual(fake.calls, 1)
        engine.tick(self.now + timedelta(seconds=5), 105)
        self.assertEqual(fake.calls, 2)

    def test_uncertain_power_delivery_retries_after_timeout(self):
        fake = Mock()
        fake.observe_power.return_value = PowerObservation('on', 'api')
        fake.power_hold.side_effect = [OSError('delivery unknown'), None]
        engine = AutomationManager(self.tvs, self.sched, self.data, fake,
                                   RuntimeConfig(confirm_online_checks=1), armed=True)
        with self.assertLogs('app.managers.automation_manager', level='ERROR'):
            engine.tick(self.now, 100)
        self.assertTrue(self.data.runtime_state(self.tv.tv_id)['blocked_until_offline'])
        engine.tick(self.now + timedelta(seconds=14), 114)
        self.assertEqual(fake.power_hold.call_count, 1)
        engine.tick(self.now + timedelta(seconds=15), 115)
        self.assertEqual(fake.power_hold.call_count, 2)

    def test_timestamp_less_legacy_guard_does_not_block_forever(self):
        fake = FakeSamsung()
        self.data.set_runtime(self.tv.tv_id, None, True)
        engine = AutomationManager(self.tvs, self.sched, self.data, fake,
                                   RuntimeConfig(confirm_online_checks=1), armed=True)
        engine.tick(self.now, 100)
        self.assertEqual(fake.calls, 1)

    def test_store_roundtrip(self):
        self.assertEqual(self.tvs.get('anessa'),self.tv)
        self.assertEqual(len(self.tvs.list()),1)

if __name__=='__main__':
    unittest.main()
