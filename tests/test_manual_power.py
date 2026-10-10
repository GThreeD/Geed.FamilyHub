import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from main import SamsungApplication
from app.models.schemas import TVConfig, ValidationError
from app.services.samsung_service import PowerConnectionNotEstablished, PowerObservation


class ManualPowerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.app = SamsungApplication(Path(temp.name))
        self.tv = TVConfig('tv', 'TV', '192.168.1.20', True,
                           {day: [] for day in ('mon','tue','wed','thu','fri','sat','sun')}, None, None).validate()
        self.app.tvs.save(self.tv)
        self.app.samsung = Mock()
        self.app.samsung.observe_power.return_value = PowerObservation('on', 'api')

    def test_sends_power_without_creating_lock_or_removing_bonus_even_in_test_mode(self):
        self.app.schedules.add_bonus('tv', 30)
        result = self.app.facade.power_off('tv')
        self.assertTrue(result['sent'])
        self.app.samsung.power_hold.assert_called_once()
        self.assertIsNone(self.app.schedules.locks.get('tv'))
        self.assertEqual(self.app.facade.get_status('tv')['bonus_remaining_seconds'], 1800)
        self.assertTrue(self.app.data.runtime_state('tv')['blocked_until_offline'])
        with self.assertRaises(ValidationError):
            self.app.facade.power_off('tv')
        self.app.samsung.power_hold.assert_called_once()

    def test_no_toggle_when_offline_or_unknown(self):
        for state in ('off', 'standby', 'unknown'):
            self.app.samsung.observe_power.return_value = PowerObservation(state, 'api')
            if state == 'unknown':
                with self.assertRaises(ValidationError):
                    self.app.facade.power_off('tv')
            else:
                self.assertFalse(self.app.facade.power_off('tv')['sent'])
        self.app.samsung.power_hold.assert_not_called()

    def test_connection_failure_before_send_allows_retry(self):
        self.app.samsung.power_hold.side_effect = PowerConnectionNotEstablished()
        with self.assertRaises(PowerConnectionNotEstablished):
            self.app.facade.power_off('tv')
        self.assertFalse(self.app.data.runtime_state('tv')['blocked_until_offline'])

    def test_uncertain_delivery_keeps_guard(self):
        self.app.samsung.power_hold.side_effect = OSError()
        with self.assertRaises(OSError):
            self.app.facade.power_off('tv')
        self.assertTrue(self.app.data.runtime_state('tv')['blocked_until_offline'])
