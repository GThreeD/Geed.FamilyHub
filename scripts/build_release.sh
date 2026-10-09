#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v npm >/dev/null || { echo 'npm is required on the build computer' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'python3 is required' >&2; exit 1; }
if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm ci --ignore-scripts)
fi
(cd frontend && npm run build)
test -s frontend/dist/index.html || { echo 'Missing built frontend' >&2; exit 1; }
python3 -m compileall -q app main.py
mkdir -p release
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/samsung-tv-control/frontend"
cp -R app "$STAGE/samsung-tv-control/"
cp main.py requirements.txt "$STAGE/samsung-tv-control/"
cp -R frontend/dist "$STAGE/samsung-tv-control/frontend/"
# Exclude bytecode, credentials, databases, logs, and local caches.
find "$STAGE" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$STAGE" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
tar -czf release/samsung-tv-control-termux.tar.gz -C "$STAGE" samsung-tv-control
shasum -a 256 release/samsung-tv-control-termux.tar.gz > release/samsung-tv-control-termux.tar.gz.sha256
echo "Release: $ROOT/release/samsung-tv-control-termux.tar.gz"
