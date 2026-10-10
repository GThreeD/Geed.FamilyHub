"""Independent server-side updater for POSIX hosts; installs backend and frontend."""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path


def main():
    root = Path(sys.argv[1]).resolve()
    parent_pid = int(sys.argv[2])
    updates = root / 'private' / 'updates'
    marker = updates / 'installing.lock'
    backup = updates / 'previous'
    staging = updates / 'staging'
    log_path = updates / 'update.log'
    try:
        archive = updates / 'download.tar.gz'
        metadata = json.loads((updates / 'ready.json').read_text())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != metadata['sha256']:
            raise RuntimeError('Prüfsumme stimmt nicht mehr')
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        with tarfile.open(archive, 'r:gz') as tar:
            for entry in tar.getmembers():
                parts = Path(entry.name).parts
                if (not parts or parts[0] != 'samsung-tv-control' or '..' in parts or
                    not (entry.isfile() or entry.isdir()) or entry.issym() or entry.islnk()):
                    raise RuntimeError('Unsicherer Archivinhalt')
            tar.extractall(staging, filter='data')
        package = staging / 'samsung-tv-control'
        for item in ('main.py', 'app', 'requirements.txt', 'frontend/dist/index.html'):
            if not (package / item).exists():
                raise RuntimeError('Fehlende Datei: ' + item)
        # Ensure a compatible Python runtime before touching the live files.
        subprocess.run([sys.executable, '-m', 'compileall', '-q', str(package / 'app'), str(package / 'main.py')], check=True, timeout=90)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(package / 'requirements.txt')],
                       check=True, timeout=240)
        time.sleep(2)  # Allow the HTTP response to reach the admin before shutdown.
        database = root / 'private' / 'samsung.db'
        if database.exists():
            # SQLite online backup handles WAL; plain file copies do not.
            with sqlite3.connect(database) as source:
                with sqlite3.connect(updates / 'samsung-before-update.db') as destination:
                    source.backup(destination)
        os.kill(parent_pid, signal.SIGTERM)
        for _ in range(40):
            try:
                os.kill(parent_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(.25)
        else:
            raise RuntimeError('Alter Server konnte nicht beendet werden')
        shutil.rmtree(backup, ignore_errors=True)
        backup.mkdir()
        targets = ('app', 'main.py', 'requirements.txt', 'frontend/dist')
        for target in targets:
            source = root / target
            dest = backup / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, dest)
            elif source.exists():
                shutil.copy2(source, dest)
        try:
            for target in targets:
                source = package / target
                dest = root / target
                if dest.is_dir():
                    shutil.rmtree(dest)
                elif dest.exists():
                    dest.unlink()
                dest.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, dest)
                else:
                    shutil.copy2(source, dest)
        except Exception:
            for target in targets:
                source = backup / target
                dest = root / target
                if dest.is_dir():
                    shutil.rmtree(dest)
                elif dest.exists():
                    dest.unlink()
                if source.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if source.is_dir():
                        shutil.copytree(source, dest)
                    else:
                        shutil.copy2(source, dest)
            raise
        (root / 'private' / 'installed-version.txt').write_text(metadata['tag'])
    except Exception as exc:
        log_path.write_text('Update fehlgeschlagen: ' + repr(exc))
    finally:
        marker.unlink(missing_ok=True)
        # Start even after an installation error, preserving the previous install.
        with (root / 'server.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-u', str(root / 'main.py')],
                             cwd=root, stdin=subprocess.DEVNULL, stdout=log,
                             stderr=subprocess.STDOUT, start_new_session=True)

if __name__ == '__main__':
    main()
