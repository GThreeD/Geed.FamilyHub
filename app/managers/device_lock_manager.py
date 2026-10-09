"""Persistent device locks, independent of schedule and bonus."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.models.schemas import ValidationError

class DeviceLockManager:
    def __init__(self, data):
        self.data = data

    def get(self, tv_id, now=None):
        now = now or datetime.now(timezone.utc)
        lock = self.data.get_tv_lock(tv_id)
        if lock and lock['expires_at'] and datetime.fromisoformat(lock['expires_at']) <= now:
            self.data.remove_tv_lock(tv_id)
            return None
        return lock

    def set(self, tv, mode, now=None):
        if mode not in ('until_tomorrow', 'indefinite'):
            raise ValidationError('Sperrmodus ungültig')
        now = now or datetime.now(timezone.utc)
        expiry = None
        if mode == 'until_tomorrow':
            local_now = now.astimezone(ZoneInfo(tv.timezone))
            tomorrow = local_now.date() + timedelta(days=1)
            midnight = datetime.combine(tomorrow, datetime.min.time(), ZoneInfo(tv.timezone))
            expiry = midnight.astimezone(timezone.utc).isoformat()
        self.data.save_tv_lock(tv.tv_id, mode, expiry, now.isoformat())
        return self.get(tv.tv_id, now)

    def clear(self, tv_id):
        self.data.remove_tv_lock(tv_id)
