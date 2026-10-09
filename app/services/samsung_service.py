import socket
from pathlib import Path

class SamsungService:
    """LAN integration only; cannot determine physical screen state with certainty."""
    def __init__(self, token_dir: Path, timeout: float=2):
        self.token_dir = Path(token_dir)
        self.token_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.timeout = timeout

    def is_reachable(self, tv) -> bool:
        """Conservative LAN signal: require both independently tested TV ports.

        A TCP connection is not proof the panel is on. If either port cannot
        be reached, fail closed for usage accounting and power commands.
        """
        for port in (8002, 9197):
            try:
                with socket.create_connection((tv.ip, port), timeout=self.timeout):
                    pass
            except OSError:
                return False
        return True

    def power_hold(self, tv, seconds: float):
        from samsungtvws import SamsungTVWS
        token_file = self.token_dir / f'{tv.tv_id}.token'
        remote = SamsungTVWS(host=tv.ip,port=8002,token_file=str(token_file),
                             timeout=15,name='SamsungTVControl')
        with remote:
            remote.hold_key('KEY_POWER',seconds)
        if token_file.exists():
            token_file.chmod(0o600)
