"""Shared retry deadline for automatic and manual power attempts."""
from datetime import datetime

MAX_POWER_RETRY_SECONDS = 15


def power_retry_remaining(runtime, now: datetime, cooldown_seconds: int) -> float:
    previous = runtime.get('last_attempt_at')
    if not previous:
        # Old guards without a timestamp must not block forever.
        return 0
    elapsed = (now - datetime.fromisoformat(previous)).total_seconds()
    return max(0, min(cooldown_seconds, MAX_POWER_RETRY_SECONDS) - elapsed)
