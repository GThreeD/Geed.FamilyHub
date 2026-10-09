from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time
from ipaddress import ip_address
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')

class ValidationError(ValueError):
    pass


def valid_time(value: str) -> time:
    if not isinstance(value, str) or len(value) != 5:
        raise ValidationError('Zeit erwartet als HH:MM')
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f'Ungueltige Uhrzeit: {value!r}') from exc
    if parsed.strftime('%H:%M') != value:
        raise ValidationError('Zeit erwartet als HH:MM')
    return parsed


def validate_windows(windows: dict) -> dict:
    if not isinstance(windows, dict) or set(windows) != set(DAYS):
        raise ValidationError('Zeitplan braucht genau mon,tue,wed,thu,fri,sat,sun')
    for day, entries in windows.items():
        if not isinstance(entries, list):
            raise ValidationError(f'{day}: Liste erwartet')
        prev_end = None
        for entry in entries:
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                raise ValidationError(f'{day}: Zeitfenster braucht [start, ende]')
            start, end = (valid_time(v) for v in entry)
            if start >= end:
                raise ValidationError(f'{day}: Zeitfenster ueber Mitternacht nicht erlaubt')
            if prev_end is not None and start < prev_end:
                raise ValidationError(f'{day}: Zeitfenster ueberlappen oder unsortiert')
            prev_end = end
    return windows


@dataclass(frozen=True)
class TVConfig:
    tv_id: str
    name: str
    ip: str
    enabled: bool
    schedule: dict
    daily_limit_minutes: int | None
    weekly_limit_minutes: int | None
    timezone: str = 'Europe/Berlin'

    def validate(self) -> 'TVConfig':
        if not self.tv_id or len(self.tv_id) > 64 or not self.tv_id.replace('-', '').replace('_', '').isalnum():
            raise ValidationError('tv_id ungueltig')
        if not self.name or len(self.name) > 100:
            raise ValidationError('Name ungueltig')
        try:
            addr = ip_address(self.ip)
        except ValueError as exc:
            raise ValidationError('IP ungueltig') from exc
        if addr.version != 4 or not addr.is_private or addr.is_loopback or addr.is_link_local:
            raise ValidationError('Nur private IPv4-LAN-Adressen erlaubt')
        if type(self.enabled) is not bool:
            raise ValidationError('enabled muss bool sein')
        validate_windows(self.schedule)
        for label, limit in [('daily', self.daily_limit_minutes), ('weekly', self.weekly_limit_minutes)]:
            if limit is not None and (type(limit) is not int or not 1 <= limit <= 10080):
                raise ValidationError(f'{label} limit: 1..10080 Minuten oder null')
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError('Zeitzone nicht gefunden') from exc
        return self


@dataclass(frozen=True)
class RuntimeConfig:
    poll_seconds: int = 5
    confirm_online_checks: int = 3
    confirm_offline_checks: int = 3
    cooldown_seconds: int = 120
    power_hold_seconds: float = 2.0

    def validate(self) -> 'RuntimeConfig':
        for field, lo, hi in [('poll_seconds', 2, 60), ('confirm_online_checks', 2, 20),
                              ('confirm_offline_checks', 2, 20), ('cooldown_seconds', 15, 3600)]:
            val = getattr(self, field)
            if type(val) is not int or not lo <= val <= hi:
                raise ValidationError(f'{field}: erwartet {lo}..{hi}')
        if type(self.power_hold_seconds) not in (int, float) or not 0.5 <= self.power_hold_seconds <= 5:
            raise ValidationError('power_hold_seconds: 0.5..5')
        return self
