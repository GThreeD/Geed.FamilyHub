from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

@dataclass
class Observation:
    online_count: int = 0
    offline_count: int = 0
    confirmed_online: bool = False
    last_monotonic: float | None = None
    last_day: str | None = None
    last_state: tuple | None = None
    dry_logged: bool = False
    last_checked_at: str | None = None
    last_reachable: bool | None = None

class AutomationManager:
    def __init__(self,tv_manager,schedule_manager,data,samsung,settings,armed=False):
        self.tvs=tv_manager
        self.schedules=schedule_manager
        self.data=data
        self.samsung=samsung
        self.settings=settings.validate()
        self.armed=armed
        self.state={}

    def tick(self, now=None, monotonic=None):
        now = now or datetime.now(timezone.utc)
        monotonic = time.monotonic() if monotonic is None else monotonic
        for tv in self.tvs.list():
            st=self.state.setdefault(tv.tv_id,Observation())
            reachable=self.samsung.is_reachable(tv)
            st.last_reachable=reachable
            st.last_checked_at=now.isoformat()
            st.online_count = st.online_count+1 if reachable else 0
            st.offline_count = st.offline_count+1 if not reachable else 0
            if st.offline_count>=self.settings.confirm_offline_checks:
                st.dry_logged=False
            was_confirmed=st.confirmed_online
            if st.online_count>=self.settings.confirm_online_checks:
                st.confirmed_online=True
            elif st.offline_count>=self.settings.confirm_offline_checks:
                st.confirmed_online=False
            # A schedule indicates permission, NOT actual consumption. Only
            # verified consecutive LAN samples are eligible for estimated usage.
            # Already recorded seconds remain in SQLite when the TV goes off.
            # Only count contiguous confirmed-online intervals with a bounded duration.
            # On slow polls/hibernation/startup/clock-day changes: do not backfill gaps.
            from app.helpers.time_helpers import day_key
            local_day=day_key(now,tv.timezone)
            interval=(monotonic-st.last_monotonic) if st.last_monotonic is not None else 0
            if (reachable and was_confirmed and st.confirmed_online and st.last_day==local_day
                and 0 < interval <= self.settings.poll_seconds*1.6):
                count=min(int(interval),self.settings.poll_seconds)
                if count:
                    before=self.schedules.evaluate(tv,now)
                    try:
                        self.schedules.add_usage(tv,count,now,before['reason'])
                        self.data.add_session_duration(tv.tv_id,count)
                    except Exception as exc:
                        logger.exception('Nutzungsbuchung fehlgeschlagen %s: %s',tv.name,exc)
                        # Fail closed for commands: never toggle on DB/accounting errors.
                        st.last_monotonic=monotonic
                        st.last_day=local_day
                        continue
            if not was_confirmed and st.confirmed_online:
                self.data.start_usage_session(tv.tv_id,now.isoformat())
            if was_confirmed and not st.confirmed_online:
                self.data.end_usage_session(tv.tv_id,now.isoformat())
            st.last_monotonic=monotonic
            st.last_day=local_day
            status=self.schedules.evaluate(tv,now)
            observation=(st.confirmed_online,status['reason'],reachable)
            if observation!=st.last_state:
                logger.info('%s erreichbar=%s bestaetigt_online=%s berechtigt=%s grund=%s heute=%ss woche=%ss bonus=%ss',
                    tv.name,reachable,st.confirmed_online,status['allowed'],status['reason'],
                    status['used_today_seconds'],status['used_week_seconds'],status['bonus_remaining_seconds'])
                st.last_state=observation
            # Offline confirmation arms future attempt, persists over restarts.
            persistent=self.data.runtime_state(tv.tv_id)
            if st.offline_count>=self.settings.confirm_offline_checks and persistent['blocked_until_offline']:
                self.data.set_runtime(tv.tv_id,persistent['last_attempt_at'],False)
                persistent=self.data.runtime_state(tv.tv_id)
            if not st.confirmed_online or not reachable or status['allowed'] or not tv.enabled:
                continue
            if persistent['blocked_until_offline']:
                continue
            if persistent['last_attempt_at']:
                previous=datetime.fromisoformat(persistent['last_attempt_at'])
                if now-previous < timedelta(seconds=self.settings.cooldown_seconds):
                    continue
            if not self.armed:
                if not st.dry_logged:
                    logger.warning('[DRY RUN] Wuerde %s ausschalten',tv.name)
                    st.dry_logged=True
                continue
            # Recheck immediately; power key is a toggle and might turn the TV ON.
            if not self.samsung.is_reachable(tv):
                continue
            # Persist guard BEFORE potentially irreversible external action.
            self.data.set_runtime(tv.tv_id,now.isoformat(),True)
            self.data.log_event(tv.tv_id,now.isoformat(),'power_attempt','KEY_POWER hold')
            try:
                self.samsung.power_hold(tv,self.settings.power_hold_seconds)
                logger.warning('%s: KEY_POWER gesendet; Wirkung nicht garantiert',tv.name)
            except Exception:
                logger.exception('%s: Power-Befehl fehlgeschlagen (kein Auto-Retry bis offline)',tv.name)
                self.data.log_event(tv.tv_id,now.isoformat(),'power_error','Fehler beim Senden')
