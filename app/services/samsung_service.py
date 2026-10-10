import socket
import json
import time
import urllib.request
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

@dataclass(frozen=True)
class PowerObservation:
    # on / standby / off / unknown; "network" means a port-only fallback.
    state: str
    source: str
    power_state: str | None = None
    port_8002: bool = False
    port_9197: bool = False


class PowerConnectionNotEstablished(ConnectionError):
    """The WebSocket connection failed before any power key was sent."""


class SamsungService:
    """LAN integration only; cannot determine physical screen state with certainty."""
    def __init__(self, token_dir: Path, timeout: float=2):
        self.token_dir = Path(token_dir)
        self.token_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.timeout = timeout

    def observe_power(self, tv) -> PowerObservation:
        """Prefer an explicit Samsung state; fall back to conservative LAN clues.

        A missing API response is not a proof of standby. In particular, one
        reachable port must not cause a power toggle on a sleeping TV.
        """
        def port_open(port):
            try:
                with socket.create_connection((tv.ip, port), timeout=self.timeout):
                    return True
            except OSError:
                return False

        def read_state():
            try:
                with urllib.request.urlopen(
                    f'http://{tv.ip}:8001/api/v2/', timeout=self.timeout
                ) as response:
                    payload = json.load(response)
                value = payload.get('device', {}).get('PowerState')
                return value.lower() if isinstance(value, str) else None
            except (OSError, ValueError, TypeError, KeyError):
                return None

        with ThreadPoolExecutor(max_workers=3) as pool:
            f_api = pool.submit(read_state)
            f_8002 = pool.submit(port_open, 8002)
            f_9197 = pool.submit(port_open, 9197)
            power = f_api.result()
            ws = f_8002.result()
            session = f_9197.result()

        if power == 'standby':
            return PowerObservation('standby', 'api', power, ws, session)
        if power == 'on':
            # A contradictory port signal can mean the panel is changing state.
            # Avoid sending a toggle until the signal stabilizes.
            state = 'on' if session else 'unknown'
            return PowerObservation(state, 'api', power, ws, session)
        if not ws and not session:
            return PowerObservation('off', 'network', power, ws, session)
        if ws and session:
            return PowerObservation('on', 'network', power, ws, session)
        return PowerObservation('unknown', 'network', power, ws, session)

    def is_reachable(self, tv) -> bool:
        """Compatibility for other callers; unknown/standby are not on."""
        return self.observe_power(tv).state == 'on'

    def power_hold(self, tv, seconds: float):
        """Send one short KEY_POWER press; never retry an uncertain delivery.

        Kept as power_hold for compatibility with existing AutomationManager and
        test adapters. The TV's explicit ON observation gates this toggle.
        """
        from samsungtvws import SamsungTVWS
        token_file = self.token_dir / f'{tv.tv_id}.token'
        remote = SamsungTVWS(host=tv.ip, port=8002, token_file=str(token_file),
                             timeout=15, name='SamsungTVControl')
        connected = False
        try:
            with remote:
                connected = True
                remote.send_key('KEY_POWER', key_press_delay=0.2)
                # A tested delay permits the TV to process the command before
                # the WebSocket closes. This does not confirm power-off.
                time.sleep(3)
        except OSError as exc:
            if not connected:
                raise PowerConnectionNotEstablished(
                    'Samsung-WebSocket vor dem Power-Befehl nicht erreichbar'
                ) from exc
            raise
        finally:
            if token_file.exists():
                token_file.chmod(0o600)
