import tempfile
import unittest
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

    def test_store_roundtrip(self):
        self.assertEqual(self.tvs.get('anessa'),self.tv)
        self.assertEqual(len(self.tvs.list()),1)

if __name__=='__main__':
    unittest.main()
