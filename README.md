# Samsung TV Control v2.1 — Backend-Patch

Kein CLI-Menü, keine Konfiguration über `main.py`, noch keine Web-UI. `python3 main.py` startet einen dauerhaft laufenden Monitor und eine **nur auf `127.0.0.1:8765` gebundene** lokale JSON-API. Diese API wird später vom UI angesprochen. Der Prozess muss laufen (auf Mac z. B. per LaunchAgent; auf Android später über Termux:Boot).

## Installation / Upgrade

1. Bei bestehender v2-Installation den Ordner `private/` mit der Datenbank und den Pairing-Tokens **sichern und unverändert übernehmen**. Nicht mit Dateien aus dem ZIP überschreiben.
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python3 main.py`

Die DB-Migrationen werden beim Start angewendet. Auf vorhandener v2-DB werden die vorhandenen Tabellen als `20261009160000_InitialCreate` in der Migrationshistorie **gebaselined**, und `20261009170000_RuntimeSettings` ergänzt die Tabelle `app_settings`. TV-Daten, Nutzungszeit und Bonus bleiben erhalten. **Vorher DB-Backup machen.** Neue Installationen erzeugen beide Migrationen automatisch.

`config.json` ist **keine Laufzeitkonfiguration** mehr. Wenn eine alte `config.json` vorhanden und die TV-Tabelle leer ist, importiert der Dienst die validierten Einstellungen und Fernseher einmalig in SQLite und benennt die Datei in `config.json.imported` um. Existieren bereits TV-Datensätze, gewinnt die DB; die JSON-Datei wird ignoriert. Danach werden Einstellungen ausschließlich aus der DB gelesen und über HTTP geändert. Der ZIP liegt zur Kompatibilität eine Legacy-`config.json` als einmalige Seed-Datei bei.

## Schichten

- `main.py` — Composition Root: Initialisierung, Monitor-Thread, HTTP-Server.
- `app/data/database_data.py` — Datenzugriffe und atomare Transaktionen.
- `app/data/migrations/migration_manager.py` — vorwärtsgerichtete SQLite-Migrationen mit `__EFMigrationsHistory`, `MigrationId`, `ProductVersion`, `AppliedAt`. Migrationen werden nur einmal und innerhalb einer SQL-Transaktion ausgeführt.
- `app/managers/` — Regeln (TV, Schedule, Settings, Automation).
- `app/services/samsung_service.py` — Samsung-LAN/WebSocket-Aufrufe.
- `app/api/handlers.py` — unabhängige Anwendungs-API.
- `app/api/http_api.py` — HTTP-Transport für die spätere Oberfläche.
- `app/models/` — Eingabevalidierung.

## HTTP-API (nur lokaler Mac)

- `GET /api/tvs`
- `PUT /api/tvs/{tv_id}` — vollständiges `TVConfig`-Objekt
- `GET /api/tvs/{tv_id}/status`
- `GET /api/tvs/{tv_id}/events?limit=100`
- `POST /api/tvs/{tv_id}/bonus` — `{"minutes":30,"expires_at":"2026-10-09T21:00:00+02:00"}` (Ablauf muss in Zukunft liegen)
- `GET /api/settings`
- `PUT /api/settings` — alle Runtime-Einstellungen als JSON, inklusive `armed` (Boolean)
- `GET /api/migrations` — Migration History

Beispiel: `curl http://127.0.0.1:8765/api/settings`

Zum Bearbeiten: `GET /api/settings` holen, Werte ändern, vollständiges Objekt außer dem read-only-Feld `id` per `PUT` senden.

**Sicherheit:** Die API hat derzeit keine Anmeldung oder CSRF-Abwehr. Sie darf deshalb **nur auf localhost** laufen; nicht per Portfreigabe, Reverse-Proxy oder LAN-Bindung veröffentlichen. Bevor ein Browser-UI im Heimnetz nutzbar gemacht wird, muss Authentifizierung/Autorisierung ergänzt werden. Standardmäßig ist `armed=false` (reiner Trockenlauf). Das UI muss den Arming-Schalter ausdrücklich freigeben. Power-Toggle bei falscher Zustandserkennung bleibt ein Restrisiko.

## Datenbank und Zeitlogik

`private/samsung.db`: `tvs`, `usage`, `bonus`, `events`, `runtime`, `app_settings`, `__EFMigrationsHistory`. SQLite WAL, FK, parametrisierte Queries. Einmalige Seed-Daten und Änderung der Settings liegen in Data, nicht in `main.py`. Das Usage-Zählen ist weiter eine LAN-Verfügbarkeits-Näherung, kein verlässlicher Bildschirm-Sensor. Bonus wird zusätzlich gewährt, wenn Zeitfenster oder Quoten nicht reichen.

## Tests

`python3 -m unittest discover -s tests -v`

Die bisherigen Tests sowie neue Tests für Migration-Idempotenz, Upgrade einer v2-Datenbank, einmaligen JSON-Import und Setting-Validierung laufen ohne echtes TV-Gerät. Der HTTP-Server ist nicht mit einem realen Fernseher end-to-end getestet.

## Git und Patch-Workflow (v2.2)

Einmalig im Projektverzeichnis:

```bash
git init
git add .
git commit -m "Baseline v2.1"
```

Danach neue Änderungen mit `git apply --check DATEI.patch` prüfen und mit
`git apply DATEI.patch` übernehmen. Nach den Tests einen Commit anlegen.
`private/`, `.venv/` und Token-Dateien werden von Git ignoriert. Bitte keine
Datenbank oder Token-Dateien mit `git add -f` einchecken.

## Zähler und Erreichbarkeit

`allowed` beschreibt **ausschließlich die Nutzungsberechtigung**, nicht den
Ist-Zustand des Fernsehers. `used_today_seconds` und `used_week_seconds` sind
**persistente kumulierte** Schätzwerte; sie bleiben nach dem Ausschalten
sichtbar und gehen erst am Tages- bzw. Wochenwechsel auf einen neuen Zeitraum.
Die v2.2-Prüfung verlangt gleichzeitig erreichbare TCP-Ports 8002 und 9197
und mehrere bestätigte Prüfzyklen. Das reduziert False-Positives, ersetzt aber
keinen echten Bildschirm-Powersensor. Die API liefert unter
`GET /api/tvs/{tv_id}/status` zusätzlich `online_observation` mit
`state` (online/offline/unknown), `reachable`, `confirmed_online` und
`last_checked_at` sowie `usage_is_estimate: true`.

Alte Zählerwerte werden durch das Patch **nicht rückwirkend korrigiert**.
Wenn Port 9197 während der Wiedergabe geschlossen ist, pausiert die neue
Erkennung die Nutzungszählung vollständig; in diesem Fall die Portprüfungen
noch einmal wiederholen, bevor die Nachsperre scharf geschaltet wird.

## v2.3 — Frontend, Auth und Rollen

**Migration:** `20261009180000_UsersAndSessions` ergänzt `users` und `auth_sessions` mit Eintrag in `__EFMigrationsHistory`. Beim Start automatisch; zuvor `private/` sichern. PIN und Muster liegen ausschließlich als PBKDF2-HMAC-SHA256 Hash mit individuellem Salt in der Datenbank. Sessions sind serverseitig gespeichert, das Cookie ist HttpOnly, SameSite=Strict (für HTTPS zusätzlich `STC_SECURE_COOKIE=1`). Schreibzugriffe benötigen einen CSRF-Token. Nach fünf Fehlversuchen wird ein Konto 15 Minuten gesperrt. PINs müssen 6–12 Ziffern enthalten; Muster brauchen 6–9 verschiedene Punkte. Muster sind weniger widerstandsfähig als lange PINs.

**Rollen:** `admin` darf Einstellungen, Nutzer, Zeitpläne und Bonus verwalten; `manager` darf Einstellungen, Zeitpläne und Bonus verwalten; `viewer` darf ausschließlich lesen. Durchsetzung erfolgt im Backend, nicht nur durch das Verbergen von UI-Aktionen. Der letzte aktive Admin kann nicht deaktiviert oder degradiert werden. Jeder Login erneuert die Sitzung des jeweiligen Kontos.

**Frontend erstmals installieren (Mac):**

```bash
cd frontend
npm install
npm run build
cd ..
python3 main.py
```

Anschließend `http://127.0.0.1:8765` öffnen. Erster Aufruf: lokalen Administrator mit PIN/Muster einrichten; danach anmelden. Die Ersteinrichtung wird **nur auf localhost** akzeptiert. Entwicklung mit `cd frontend && npm run dev`, Backend parallel auf Port 8765; Dev-Proxy verweist auf localhost. Das React/Vite-Build wird statisch durch den Python-Server ausgeliefert; Node ist zur Laufzeit nicht erforderlich.

**Sicherheit im Heimnetz:** Voreinstellung bleibt `127.0.0.1:8765`. `STC_HOST=0.0.0.0` bindet zwar im LAN, sollte aber **nicht ohne TLS am Reverse-Proxy und `STC_SECURE_COOKIE=1`** aktiviert werden, da PIN/Muster sonst unverschlüsselt übertragen werden. Keine Portweiterleitungen ins Internet einrichten. Es gibt momentan keinen Self-Service-Zugangsdaten-Reset; Zugriffsverlust des einzigen Administrators benötigt eine kontrollierte Wiederherstellung. `private/` inklusive Datenbank sichern.

Die v2.3-Oberfläche bietet Dashboard, TV-Zeitpläne, Limits, Bonus, Einstellungen und Benutzerverwaltung. Die **Erstanlage neuer TVs** ist noch nicht im UI enthalten (bestehende Datensätze funktionieren). Ebenso fehlen bislang Nutzungs-Sessions/Charts und ein Audit-Log für Benutzeraktionen. `PowerState` bleibt durch LAN-Prüfung geschätzt; der automatische Power-Toggle sollte zunächst nicht aktiviert werden. Die `config.json` wird weiterhin nur einmalig importiert.

**API:** `/api/auth/setup-status`, `/api/auth/setup`, `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, `GET/POST /api/users`, `PATCH /api/users/{id}`. Die bisherigen `/api/tvs`, `/api/settings` usw. sind jetzt authentifizierungspflichtig. Beim Login wird `csrf_token` zurückgegeben, der bei jedem nicht lesenden API-Aufruf in `X-CSRF-Token` gesendet werden muss. Ein Reload bezieht über `/api/auth/me` einen neuen Token. Kein Login via URL-/Query-Parameter.

**Tests:** `python3 -m unittest discover -s tests -v`. Das React-Build erfordert zuvor `npm install`. Der Python-Code lässt sich unabhängig davon ausführen.

## v2.5 – Geräteverwaltung, Statistiken und manuelle Sperren

- Geräteverwaltung (Admin, Desktop): Anlegen, Name/IP ändern und Löschen. Löschen entfernt die Nutzungsdaten des TV.
- Statistik: Bisherige Tagessekunden und neue beobachtete Nutzungssitzungen ab v2.5.
- Manuelle Sperre (Admin/Manager): bis morgen 00:00 Uhr in TV-Zeitzone oder unbegrenzt bis Freigabe.
- `manual_lock` übersteuert Zeitpläne **und Bonuszeit**. Die echte Abschaltung benötigt aktivierte Automatisierung und erreichbaren TV.
- Neue EF-Core-artige Migrationen `UsageSessions` und `TemporaryTvLocks` (insgesamt sechs).
- PIN-/Muster-Authentifizierung und CSRF gelten auch für neue API-Endpunkte.
- Bereits bestehende Nutzungszeit kann nicht rückwirkend in Sitzungen aufgeteilt werden.

Bonuszeit gilt in der Zeitzone des Fernsehers nur bis zum Ende des aktuellen Tages.
Bei mehreren Zeitfenstern an diesem Tag verlängert die Gutschrift das aktuelle
Fenster um die vergebenen Minuten (z. B. 05–10 Uhr + 30 Minuten bis 10:30 Uhr),
höchstens bis zum nächsten Fenster oder bis Mitternacht. Zwischen Fenstern
beginnt die Bonuszeit sofort und läuft für die vergebenen Minuten. Zeitplan-Ausnahmen
werden dabei berücksichtigt. Ein älterer API-Client kann über `expires_at` ein
früheres Ablaufdatum angeben, aber diese Grenzen nicht verlängern.

Unter Einstellungen → Deine Übersicht kann jedes Benutzerkonto die Kacheln
„Fernseher“, „Online erkannt“ und „Aktive Sperren“ einzeln ausblenden. Die Auswahl
wird im Konto gespeichert und gilt auch auf anderen Geräten. Benutzer mit
Leserechten können ihre eigene Übersicht ebenfalls anpassen.

Wenn ein Ausschaltversuch nicht zu bestätigtem Standby führt, darf die Steuerung
nach spätestens 15 Sekunden erneut Power senden. Kürzere eingestellte Wartezeiten
bleiben wirksam. Jeder automatische Versuch setzt weiterhin ein gesperrtes,
aktiviertes Gerät, eingeschalteten Sperrmodus und eine frische ON-Erkennung direkt
vor dem Senden voraus. Bei OFF, Standby oder unbekanntem Zustand wird nicht erneut
gesendet. Das gilt auch für den manuellen Power-Befehl im Geräte-Popup.

Die Nutzungszählung liest den Tages- und Wochenstand bei jeder Auswertung aus
SQLite und setzt nach einem Update oder Neustart auf diesem Stand fort. Sie bucht
die tatsächliche Zeit zwischen aufeinanderfolgenden bestätigten ON-Messungen,
einschließlich üblicher Netzwerkverzögerungen. Unbeobachtete Neustartzeiten und
lange Messlücken werden nicht rückwirkend als Nutzung gebucht.
