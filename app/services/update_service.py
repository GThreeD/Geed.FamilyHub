"""Pinned GitHub release updater; only verified app files are eligible."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path
from app.models.schemas import ValidationError

REPO = 'GThreeD/Geed.FamilyHub'
API_URL = f'https://api.github.com/repos/{REPO}/releases/latest'
ARCHIVE = 'samsung-tv-control-termux.tar.gz'
MAX_BYTES = 35 * 1024 * 1024

class UpdateService:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.stage = self.root / 'private' / 'updates'

    @staticmethod
    def _get(url: str, limit: int) -> bytes:
        request = urllib.request.Request(url, headers={'User-Agent': 'Geed-FamilyHub-Updater', 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(request, timeout=25) as response:
            if response.status != 200:
                raise ValidationError('Release-Download fehlgeschlagen')
            data = response.read(limit + 1)
        if len(data) > limit:
            raise ValidationError('Release-Datei zu groß')
        return data

    def latest(self):
        release = json.loads(self._get(API_URL, 256 * 1024))
        assets = {asset['name']: asset['browser_download_url'] for asset in release.get('assets', [])}
        if ARCHIVE not in assets or ARCHIVE + '.sha256' not in assets:
            raise ValidationError('Release ohne Paket oder Prüfsumme')
        return {'tag': release['tag_name'], 'url': assets[ARCHIVE], 'checksum_url': assets[ARCHIVE + '.sha256'], 'page': release['html_url']}

    def prepare(self):
        release = self.latest()
        checksum_text = self._get(release['checksum_url'], 4096).decode('utf-8')
        lines = [line for line in checksum_text.splitlines() if line.strip()]
        expected = None
        for line in lines:
            fields = line.split()
            if len(fields) == 2 and fields[1].lstrip('*').endswith(ARCHIVE) and len(fields[0]) == 64:
                expected = fields[0].lower()
        if expected is None or any(c not in '0123456789abcdef' for c in expected):
            raise ValidationError('Ungültige SHA-256-Prüfsumme')
        if any(urlsplit(release[field]).scheme != 'https' or urlsplit(release[field]).hostname != 'github.com'
               for field in ('url','checksum_url')):
            raise ValidationError('Unerwarteter Download-Host')
        content = self._get(release['url'], MAX_BYTES)
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            raise ValidationError('SHA-256-Prüfung fehlgeschlagen')
        self.stage.mkdir(mode=0o700, parents=True, exist_ok=True)
        archive = self.stage / 'download.tar.gz'
        archive.write_bytes(content)
        # Validate archive before allowing a separate privileged install action.
        with tarfile.open(archive, 'r:gz') as tar:
            members = tar.getmembers()
            if len(members) > 3000:
                raise ValidationError('Zu viele Dateien im Paket')
            for item in members:
                parts = Path(item.name).parts
                if (not parts or parts[0] != 'samsung-tv-control' or
                    '..' in parts or item.issym() or item.islnk() or item.isdev() or
                    not (item.isfile() or item.isdir())):
                    raise ValidationError('Unsicherer Archivinhalt')
            required = {'samsung-tv-control/main.py', 'samsung-tv-control/frontend/dist/index.html'}
            if not required.issubset({item.name for item in members}):
                raise ValidationError('Unvollständiges Release')
        (self.stage / 'ready.json').write_text(json.dumps({'tag': release['tag'], 'sha256': actual}))
        return {'tag': release['tag'], 'sha256': actual, 'ready': True}

    def install(self):
        ready_file = self.stage / 'ready.json'
        archive = self.stage / 'download.tar.gz'
        if not ready_file.is_file() or not archive.is_file():
            raise ValidationError('Bitte Release zuerst herunterladen')
        meta = json.loads(ready_file.read_text())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != meta['sha256']:
            raise ValidationError('Release-Prüfsumme geändert')
        # The updater runs on the server, regardless of the client browser OS.
        # Authentication and authorization are enforced by the HTTP API.
        marker = self.stage / 'installing.lock'
        try:
            descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        except FileExistsError:
            raise ValidationError('Update wird bereits installiert')
        try:
            subprocess.Popen(
                [sys.executable, '-m', 'app.services.update_worker', str(self.root), str(os.getpid())],
                cwd=self.root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True,
            )
        except Exception:
            marker.unlink(missing_ok=True)
            raise
        return {'ok': True, 'message': 'Update gestartet, Server startet neu'}
