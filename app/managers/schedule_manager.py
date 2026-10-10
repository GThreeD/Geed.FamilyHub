from __future__ import annotations
import json
from datetime import date
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from app.helpers.time_helpers import day_key, week_key, inside_window, MAX_USAGE_INTERVAL_SECONDS
from app.models.schemas import ValidationError, DAYS

class ScheduleManager:
    def __init__(self, data):
        self.data = data
        from app.managers.device_lock_manager import DeviceLockManager
        self.locks = DeviceLockManager(data)

    def evaluate(self, tv, now: datetime):
        now_utc = now.astimezone(timezone.utc)
        usage = self.data.usage_totals(tv.tv_id,day_key(now,tv.timezone),week_key(now,tv.timezone))
        daily_ok = tv.daily_limit_minutes is None or usage['day'] < tv.daily_limit_minutes * 60
        weekly_ok = tv.weekly_limit_minutes is None or usage['week'] < tv.weekly_limit_minutes * 60
        local_now = now.astimezone(ZoneInfo(tv.timezone))
        exception = self.data.schedule_exception_for_date(tv.tv_id, local_now.date().isoformat())
        if exception:
            # The exception replaces the regular windows for the whole date range.
            custom = json.loads(exception['windows_json'])
            current_time = local_now.strftime('%H:%M')
            scheduled = any(start <= current_time < end for start,end in custom)
        else:
            scheduled = inside_window(tv.schedule, now, tv.timezone)
        bonus_totals = self.data.bonus_totals(tv.tv_id, now_utc.isoformat())
        bonus = bonus_totals['granted'] - bonus_totals['consumed']
        regular_allowed = tv.enabled and scheduled and daily_ok and weekly_ok
        allowed = tv.enabled and (regular_allowed or bonus > 0)
        reason = ('disabled' if not tv.enabled else 'schedule_or_limit' if not allowed
                  else 'regular' if regular_allowed else 'bonus')
        lock = self.locks.get(tv.tv_id,now_utc)
        if lock:
            allowed = False
            reason = 'manual_lock'
        return {'locked':bool(lock),'lock':lock,'allowed':allowed,'reason':reason,'regular_allowed':regular_allowed,
                'bonus_granted_seconds':bonus_totals['granted'],
                'bonus_consumed_seconds':bonus_totals['consumed'],'bonus_remaining_seconds':bonus,'used_today_seconds':usage['day'],
                'used_week_seconds':usage['week'],'within_schedule':scheduled,
                'schedule_exception':exception['name'] if exception else None}

    def bonus_expiry(self, tv, minutes: int, now: datetime):
        local = now.astimezone(ZoneInfo(tv.timezone))
        midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        exception = self.data.schedule_exception_for_date(tv.tv_id, local.date().isoformat())
        windows = json.loads(exception['windows_json']) if exception else tv.schedule[DAYS[local.weekday()]]
        if len(windows) <= 1:
            return midnight.astimezone(timezone.utc)
        # Bonus between windows starts immediately; within a window it extends its end.
        base = local.astimezone(timezone.utc)
        next_start = midnight.astimezone(timezone.utc)
        for start, end in windows:
            start_at = local.replace(hour=int(start[:2]), minute=int(start[3:]), second=0, microsecond=0)
            end_at = local.replace(hour=int(end[:2]), minute=int(end[3:]), second=0, microsecond=0)
            if start_at <= local < end_at:
                base = end_at.astimezone(timezone.utc)
            elif start_at > local:
                next_start = start_at.astimezone(timezone.utc)
                break
        return min(base + timedelta(minutes=minutes), next_start, midnight.astimezone(timezone.utc))

    def add_bonus(self, tv_id: str, minutes: int, expires_at: datetime | None = None, now: datetime | None = None):
        if type(minutes) is not int or not 1 <= minutes <= 720:
            raise ValidationError('Bonus: 1 bis 720 ganze Minuten')
        now = now or datetime.now(timezone.utc)
        from app.managers.tv_manager import TVManager
        tv = TVManager(self.data).get(tv_id)
        if tv is None:
            raise ValidationError('TV nicht gefunden')
        expiry = self.bonus_expiry(tv, minutes, now)
        if expires_at is not None:
            if expires_at.tzinfo is None or expires_at <= now:
                raise ValidationError('Ablauf muss in der Zukunft liegen (mit Zeitzone)')
            # Older clients may request seven days; server policy always takes precedence.
            expiry = min(expiry, expires_at.astimezone(timezone.utc))
        self.data.grant_bonus(tv_id,minutes*60,expiry.isoformat(),now.astimezone(timezone.utc).isoformat())
        self.data.log_event(tv_id,now.isoformat(),'bonus_granted',f'{minutes} min bis {expiry.isoformat()}')

    def add_usage(self, tv, seconds: int, now: datetime, reason: str):
        if type(seconds) is not int or not 0 < seconds <= MAX_USAGE_INTERVAL_SECONDS:
            raise ValidationError(f'Nutzungsintervall ausserhalb 1..{MAX_USAGE_INTERVAL_SECONDS}s')
        bonus_to_consume = seconds if reason == 'bonus' else 0
        self.data.record_usage(tv.tv_id,day_key(now,tv.timezone),week_key(now,tv.timezone),
                               seconds,bonus_to_consume,now.astimezone(timezone.utc).isoformat())

    def list_exceptions(self, tv_id):
        if not self.data.list_tvs() or tv_id not in {tv['tv_id'] for tv in self.data.list_tvs()}:
            raise ValidationError('TV nicht gefunden')
        rows = self.data.list_schedule_exceptions(tv_id)
        return [{**r, 'windows': json.loads(r['windows_json'])} for r in rows]

    def create_exception(self, tv_id, payload):
        if not isinstance(payload, dict) or set(payload) != {'name','start_date','end_date','windows'}:
            raise ValidationError('name, start_date, end_date und windows erforderlich')
        name = payload['name']
        if not isinstance(name,str) or not 1 <= len(name.strip()) <= 80:
            raise ValidationError('Name muss 1 bis 80 Zeichen enthalten')
        try:
            start = date.fromisoformat(payload['start_date'])
            end = date.fromisoformat(payload['end_date'])
        except (ValueError, TypeError):
            raise ValidationError('Ungültiges ISO-Datum')
        if end < start or (end-start).days > 366:
            raise ValidationError('Datumsbereich muss zwischen 1 und 367 Tagen liegen')
        windows = payload['windows']
        if not isinstance(windows,list) or len(windows)>12:
            raise ValidationError('Maximal 12 Zeitfenster')
        previous_end = ''
        for window in windows:
            if not isinstance(window,list) or len(window)!=2 or not all(isinstance(x,str) for x in window):
                raise ValidationError('Zeitfenster muss [Start, Ende] sein')
            a,b = window
            try:
                if len(a)!=5 or len(b)!=5:
                    raise ValueError()
                from datetime import time as time_type
                time_type.fromisoformat(a)
                time_type.fromisoformat(b)
            except ValueError:
                raise ValidationError('Uhrzeit muss HH:MM sein')
            if a>=b or a<previous_end:
                raise ValidationError('Zeitfenster müssen sortiert und überschneidungsfrei sein')
            previous_end=b
        if tv_id not in {tv['tv_id'] for tv in self.data.list_tvs()}:
            raise ValidationError('TV nicht gefunden')
        return self.data.create_schedule_exception(tv_id,name.strip(),start.isoformat(),end.isoformat(),
                        json.dumps(windows),datetime.now(timezone.utc).isoformat())

    def delete_exception(self,tv_id,exception_id):
        if not self.data.remove_schedule_exception(tv_id,exception_id):
            raise ValidationError('Ausnahme nicht gefunden')
