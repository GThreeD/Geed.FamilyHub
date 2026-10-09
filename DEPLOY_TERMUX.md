# Deployment: Samsung TV Control on Termux

## Build on macOS

Run `bash scripts/build_release.sh` from the repository root. This executes
`npm run build` (Vite minifies production JS/CSS) and packages **only** compiled
frontend assets and backend Python source into
`release/samsung-tv-control-termux.tar.gz`. No `private/`, tokens, DB,
`.env`, or `node_modules` are included.

## Copy to the Huawei

Install Termux from F-Droid; use Termux:Boot later for automatic startup.
Transfer the tarball **without exposing tokens**, e.g. via a USB file transfer
or `scp` over trusted LAN. In Termux, place the tarball in `$HOME` and run:

```sh
pkg update
pkg install -y tar python
# Copy install_termux.sh from scripts/ to Termux HOME as well.
bash install_termux.sh samsung-tv-control-termux.tar.gz
~/.local/bin/start-samsung-tv-control
```

For local-only access behind a future HTTPS reverse proxy, run:

```sh
STC_HOST=127.0.0.1 ~/.local/bin/start-samsung-tv-control
```

**First admin:** The backend intentionally permits `/api/auth/setup` only
from `127.0.0.1` / `::1`, even if the website is viewed from another device.
Create the first admin directly on Huawei via a localhost POST; follow the
request shape from `tests/test_auth.py` and never put credentials into shell
history. Do not make `/api/auth/setup` remotely accessible as a shortcut.

## Performance / architecture

- Vite outputs minified static files with content hashes; the Huawei does not
  require Node.js.
- Python `compileall` generates `.pyc` on the target for faster module imports;
  it does **not** compile CPython into a native Android application or
  materially accelerate the ongoing TV-polling loop (mostly network I/O).
- A macOS PyInstaller/Nuitka executable cannot run on Termux/Android. Native
  builds would need Android-compatible tooling and native dependencies.
- For 2-3 TVs, network latency and polling interval are usually more relevant
  than Python execution speed.
- PWA installation from a different device generally needs trusted HTTPS,
  including a correctly configured proxy and cookies. Plain LAN HTTP is not
  sufficient; `STC_SECURE_COOKIE=1` must be enabled behind HTTPS once proxy
  headers/route handling are verified.
- Keep Termux alive by disabling Huawei battery optimization; configure
  Termux:Boot only after manual testing and arrange SQLite backups.
