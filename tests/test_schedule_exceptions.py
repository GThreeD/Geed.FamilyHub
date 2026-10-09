import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from app.data.database_data import DatabaseData
from app.managers.tv_manager import TVManager
from app.managers.schedule_manager import ScheduleManager
from app.models.schemas import TVConfig, ValidationError


class ExceptionsTests(unittest.TestCase):
    def test_override_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = DatabaseData(Path(tmp) / 'test.db')
            regular = {day: [['09:00', '21:00']] for day in ('mon','tue','wed','thu','fri','sat','sun')}
            tv = TVConfig('child','Child','192.168.3.25',True,regular,None,None).validate()
            TVManager(data).save(tv)
            manager = ScheduleManager(data)
            now = datetime(2026,12,23,11,30,tzinfo=ZoneInfo('Europe/Berlin'))
            self.assertTrue(manager.evaluate(tv,now)['within_schedule'])
            manager.create_exception('child', {'name':'Ferien','start_date':'2026-12-20',
                'end_date':'2026-12-31','windows':[['14:00','18:00']]})
            state = manager.evaluate(tv,now)
            self.assertFalse(state['within_schedule'])
            self.assertEqual(state['schedule_exception'],'Ferien')
            self.assertTrue(manager.evaluate(tv,now.replace(hour=15))['within_schedule'])
            with self.assertRaises(ValueError):
                manager.create_exception('child', {'name':'Überlappung','start_date':'2026-12-22',
                    'end_date':'2026-12-24','windows':[]})
            with self.assertRaises(ValidationError):
                manager.create_exception('child', {'name':'Fehler','start_date':'2027-01-01',
                    'end_date':'2027-01-02','windows':[['20:00','08:00']]})
            exception_id = manager.list_exceptions('child')[0]['id']
            manager.delete_exception('child',exception_id)
            self.assertTrue(manager.evaluate(tv,now)['within_schedule'])


if __name__ == '__main__':
    unittest.main()
