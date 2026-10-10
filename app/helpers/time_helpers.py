from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.schemas import DAYS, valid_time

MAX_USAGE_INTERVAL_SECONDS = 120


def day_key(now: datetime, timezone: str) -> str:
    return now.astimezone(ZoneInfo(timezone)).date().isoformat()


def week_key(now: datetime, timezone: str) -> str:
    local = now.astimezone(ZoneInfo(timezone))
    year, week, _ = local.isocalendar()
    return f'{year}-W{week:02d}'


def inside_window(schedule: dict, now: datetime, timezone: str) -> bool:
    local = now.astimezone(ZoneInfo(timezone))
    minute = local.hour * 60 + local.minute
    for start, end in schedule[DAYS[local.weekday()]]:
        a = valid_time(start)
        b = valid_time(end)
        if a.hour * 60 + a.minute <= minute < b.hour * 60 + b.minute:
            return True
    return False
