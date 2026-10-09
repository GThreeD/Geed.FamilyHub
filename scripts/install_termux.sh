#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo 'Usage: bash install_termux.sh path/to/samsung-tv-control-termux.tar.gz' >&2
  exit 2
fi
ARCHIVE="$(realpath "$1")"
test -f "$ARCHIVE" || { echo "Archive missing: $ARCHIVE" >&2; exit 1; }
pkg update
pkg install -y python openssh
APP_ROOT="$HOME/samsung-tv-control"
mkdir -p "$APP_ROOT" "$HOME/.local/bin"
# Do not overwrite an existing private directory during upgrades.
if [[ -f "$APP_ROOT/main.py" ]]; then
  cp -p "$APP_ROOT/main.py" "$APP_ROOT/main.py.previous"
fi
tar -xzf "$ARCHIVE" -C "$HOME"
cd "$APP_ROOT"
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m compileall -q app main.py
mkdir -p private/tokens
chmod 700 private private/tokens
cat > "$HOME/.local/bin/start-samsung-tv-control" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$HOME/samsung-tv-control"
exec .venv/bin/python main.py
SH
chmod 700 "$HOME/.local/bin/start-samsung-tv-control"
echo 'Installed. Start with: ~/.local/bin/start-samsung-tv-control'
echo 'WARNING: server binds to 0.0.0.0:8765 by default. Set STC_HOST=127.0.0.1 when using an HTTPS reverse proxy.'
echo 'Set up the first admin locally on the Huawei: /api/auth/setup accepts only localhost.'
