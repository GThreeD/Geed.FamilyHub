from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from app.helpers.power_helpers import power_retry_remaining

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
    last_power_state: str = "unknown"
    last_power_source: str = "unknown"

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
            # Older Samsung adapters and test doubles only expose is_reachable.
            if hasattr(self.samsung, 'observe_power'):
                probe=self.samsung.observe_power(tv)
                power_state=probe.state
                power_source=probe.source
            else:
                power_state='on' if self.samsung.is_reachable(tv) else 'off'
                power_source='legacy'
            reachable=(power_state=='on')
            confirmed_off=(power_state in ('standby', 'off'))
            st.last_power_state=power_state
            st.last_power_source=power_source
            st.last_reachable=reachable
            st.last_checked_at=now.isoformat()
            st.online_count = st.online_count+1 if reachable else 0
            st.offline_count = st.offline_count+1 if confirmed_off else 0
            # Unknown must not be used as evidence of ON or OFF.
            if power_state=='unknown':
                st.online_count=0
                st.offline_count=0
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
            observation=(st.confirmed_online,status['reason'],reachable,power_state,power_source)
            if observation!=st.last_state:
                logger.info('%s power=%s quelle=%s erreichbar=%s bestaetigt_online=%s berechtigt=%s grund=%s heute=%ss woche=%ss bonus=%ss',
                    tv.name,power_state,power_source,reachable,st.confirmed_online,status['allowed'],status['reason'],
                    status['used_today_seconds'],status['used_week_seconds'],status['bonus_remaining_seconds'])
                st.last_state=observation
            # A confirmed OFF cycle ends the prior power attempt. Clear both
            # the toggle guard and its cooldown: switching the TV back ON is a
            # new power cycle, which should be enforced promptly. Otherwise the
            # guard expires after at most 15 seconds, with a fresh ON check below.
            persistent=self.data.runtime_state(tv.tv_id)
            if st.offline_count>=self.settings.confirm_offline_checks and (
                persistent['blocked_until_offline'] or persistent['last_attempt_at']
            ):
                self.data.set_runtime(tv.tv_id,None,False)
                logger.info('%s: Standby/Offline bestaetigt; Power-Sperre zurueckgesetzt',tv.name)
                persistent=self.data.runtime_state(tv.tv_id)
            if not st.confirmed_online or not reachable or status['allowed'] or not tv.enabled:
                continue
            wait = power_retry_remaining(persistent, now, self.settings.cooldown_seconds)
            if wait > 0:
                logger.debug('%s: Power-Versuch blockiert; neuer Versuch in %.1fs bei erneutem ON', tv.name, wait)
                continue
            if not self.armed:
                if not st.dry_logged:
                    logger.warning('[DRY RUN] Wuerde %s ausschalten',tv.name)
                    st.dry_logged=True
                continue
            # Recheck immediately; power key is a toggle and might turn the TV ON.
            if hasattr(self.samsung, 'observe_power'):
                if self.samsung.observe_power(tv).state != 'on':
                    continue
            elif not self.samsung.is_reachable(tv):
                continue
            # Persist guard BEFORE potentially irreversible external action.
            self.data.set_runtime(tv.tv_id,now.isoformat(),True)
            self.data.log_event(tv.tv_id,now.isoformat(),'power_attempt','KEY_POWER short press')
            try:
                self.samsung.power_hold(tv,self.settings.power_hold_seconds)
                logger.warning('%s: KEY_POWER gesendet; Wirkung nicht garantiert',tv.name)
            except Exception as exc:
                from app.services.samsung_service import PowerConnectionNotEstablished
                if isinstance(exc, PowerConnectionNotEstablished):
                    # Nothing was sent; next cycle may retry after a fresh ON check.
                    self.data.set_runtime(tv.tv_id,None,False)
                    logger.warning('%s: Keine WebSocket-Verbindung; neuer Versuch nach erneuter ON-Pruefung',tv.name)
                    continue
                logger.exception('%s: Power-Befehl unklar/fehlgeschlagen (Retry nach maximal 15s bei erneutem ON)',tv.name)
                self.data.log_event(tv.tv_id,now.isoformat(),'power_error','Fehler beim Senden')
