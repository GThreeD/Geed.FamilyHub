import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from app.data.database_data import DatabaseData
from app.managers.schedule_manager import ScheduleManager
from app.managers.tv_manager import TVManager
from app.models.schemas import TVConfig


class BonusExpiryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.data = DatabaseData(Path(temp.name) / 'db.sqlite')
        self.manager = ScheduleManager(self.data)
        self.tvs = TVManager(self.data)
        self.now = datetime(2026, 10, 10, 9, tzinfo=ZoneInfo('Europe/Berlin'))
        self.tv = TVConfig('tv', 'TV', '192.168.1.20', True,
                           {day: [['05:00', '10:00'], ['17:00', '20:00']]
                            for day in ('mon','tue','wed','thu','fri','sat','sun')}, None, None).validate()
        self.tvs.save(self.tv)

    def grant(self, now=None, minutes=30, expires_at=None):
        self.manager.add_bonus('tv', minutes, expires_at, now=now or self.now)
        return datetime.fromisoformat(self.data.list_bonus_grants('tv')[0]['expires_at'])

    def test_current_window_extended_and_credit_not_carried_to_evening(self):
        expiry = self.grant()
        self.assertEqual(expiry, self.now.replace(hour=10, minute=30))
        self.assertEqual(self.manager.evaluate(self.tv, expiry - timedelta(seconds=1))['bonus_remaining_seconds'], 1800)
        self.assertEqual(self.manager.evaluate(self.tv, expiry)['bonus_remaining_seconds'], 0)
        self.assertFalse(self.manager.evaluate(self.tv, expiry)['allowed'])
        self.assertEqual(self.manager.evaluate(self.tv, self.now.replace(hour=17))['bonus_remaining_seconds'], 0)

    def test_bonus_between_windows_starts_now_and_ends_before_next_window(self):
        self.assertEqual(self.grant(now=self.now.replace(hour=12)), self.now.replace(hour=12, minute=30))
        self.assertEqual(self.grant(minutes=720), self.now.replace(hour=17))

    def test_never_carries_over_local_midnight(self):
        self.assertEqual(self.grant(now=self.now.replace(hour=23, minute=50)),
                         (self.now + timedelta(days=1)).replace(hour=0))

    def test_single_or_no_window_expires_at_midnight(self):
        for windows in ([['05:00', '10:00']], []):
            self.tv = replace(self.tv, schedule={day: windows for day in self.tv.schedule})
            self.tvs.save(self.tv)
            self.assertEqual(self.grant(), (self.now + timedelta(days=1)).replace(hour=0))

    def test_legacy_client_cannot_extend_expiry(self):
        self.assertEqual(self.grant(expires_at=self.now + timedelta(days=7)), self.now.replace(hour=10, minute=30))

    def test_exception_windows_control_expiry(self):
        self.data.create_schedule_exception('tv', 'Ferien', '2026-10-10', '2026-10-10',
                                            '[["08:00","11:00"],["15:00","18:00"]]', self.now.isoformat())
        self.assertEqual(self.grant(), self.now.replace(hour=11, minute=30))

    def test_midnight_uses_tv_timezone_on_dst_day(self):
        self.tv = replace(self.tv, schedule={day: [] for day in self.tv.schedule})
        self.tvs.save(self.tv)
        now = datetime(2026, 10, 25, 0, 30, tzinfo=ZoneInfo('Europe/Berlin'))
        expiry = self.grant(now=now)
        self.assertEqual(expiry, datetime(2026, 10, 25, 23, tzinfo=timezone.utc))
