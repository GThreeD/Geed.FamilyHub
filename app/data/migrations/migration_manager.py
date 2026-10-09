"""EF Core style forward-only migration history for SQLite."""
import sqlite3
from datetime import datetime, timezone

BASELINE = '20261009160000_InitialCreate'
SETTINGS = '20261009170000_RuntimeSettings'
AUTH = '20261009180000_UsersAndSessions'
EXCEPTIONS = '20261009190000_ScheduleExceptions'
SESSIONS = '20261009200000_UsageSessions'
LOCKS = '20261009210000_TemporaryTvLocks'

class MigrationManager:
    def __init__(self, db):
        self.db = db

    def apply(self):
        # sqlite3.executescript implicitly commits: keep each migration in one explicit transaction.
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS __EFMigrationsHistory
            (MigrationId TEXT PRIMARY KEY, ProductVersion TEXT NOT NULL,
             AppliedAt TEXT NOT NULL)''')
        current = {row[0] for row in self.db.execute('SELECT MigrationId FROM __EFMigrationsHistory')}
        legacy = self.db.execute('PRAGMA user_version').fetchone()[0]
        if legacy > 6:
            raise RuntimeError('Datenbank stammt aus einer neueren Version')
        if BASELINE not in current:
            if legacy >= 1 or self._exists('tvs'):
                # v2 installed schema already; do not drop data or recreate tables.
                self._record(BASELINE)
            else:
                self._sql('''
                    CREATE TABLE tvs (tv_id TEXT PRIMARY KEY, name TEXT NOT NULL, ip TEXT NOT NULL UNIQUE,
                      enabled INTEGER NOT NULL CHECK(enabled IN (0,1)), timezone TEXT NOT NULL,
                      daily_limit_minutes INTEGER, weekly_limit_minutes INTEGER, schedule_json TEXT NOT NULL);
                    CREATE TABLE usage (tv_id TEXT NOT NULL REFERENCES tvs(tv_id) ON DELETE CASCADE,
                      period_type TEXT NOT NULL CHECK(period_type IN ('day','week')),
                      period_key TEXT NOT NULL, seconds INTEGER NOT NULL DEFAULT 0 CHECK(seconds >= 0),
                      PRIMARY KEY(tv_id, period_type, period_key));
                    CREATE TABLE bonus (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      tv_id TEXT NOT NULL REFERENCES tvs(tv_id) ON DELETE CASCADE,
                      granted_seconds INTEGER NOT NULL CHECK(granted_seconds > 0),
                      consumed_seconds INTEGER NOT NULL DEFAULT 0 CHECK(consumed_seconds >= 0),
                      expires_at TEXT NOT NULL, created_at TEXT NOT NULL,
                      CHECK(consumed_seconds <= granted_seconds));
                    CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, tv_id TEXT NOT NULL,
                      timestamp TEXT NOT NULL, kind TEXT NOT NULL, details TEXT NOT NULL);
                    CREATE INDEX idx_bonus_available ON bonus(tv_id,expires_at);
                    CREATE INDEX idx_events_time ON events(tv_id,timestamp);
                    CREATE TABLE runtime (tv_id TEXT PRIMARY KEY REFERENCES tvs(tv_id) ON DELETE CASCADE,
                      last_attempt_at TEXT, blocked_until_offline INTEGER NOT NULL DEFAULT 0);
                ''', BASELINE)
        current = {row[0] for row in self.db.execute('SELECT MigrationId FROM __EFMigrationsHistory')}
        if SETTINGS not in current:
            self._sql('''CREATE TABLE app_settings (
                id INTEGER PRIMARY KEY CHECK(id=1),
                poll_seconds INTEGER NOT NULL CHECK(poll_seconds BETWEEN 2 AND 60),
                confirm_online_checks INTEGER NOT NULL CHECK(confirm_online_checks BETWEEN 2 AND 20),
                confirm_offline_checks INTEGER NOT NULL CHECK(confirm_offline_checks BETWEEN 2 AND 20),
                cooldown_seconds INTEGER NOT NULL CHECK(cooldown_seconds BETWEEN 15 AND 3600),
                power_hold_seconds REAL NOT NULL CHECK(power_hold_seconds BETWEEN 0.5 AND 5),
                armed INTEGER NOT NULL DEFAULT 0 CHECK(armed IN (0,1)));
                INSERT INTO app_settings VALUES(1,5,3,3,120,2.0,0);
            ''', SETTINGS)
        current = {row[0] for row in self.db.execute('SELECT MigrationId FROM __EFMigrationsHistory')}
        if AUTH not in current:
            self._sql('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','manager','viewer')),
                credential_type TEXT NOT NULL CHECK(credential_type IN ('pin','pattern')),
                secret_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                csrf_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at);
            ''', AUTH)
        current = {row[0] for row in self.db.execute('SELECT MigrationId FROM __EFMigrationsHistory')}
        if EXCEPTIONS not in current:
            self._sql('''CREATE TABLE IF NOT EXISTS schedule_exceptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tv_id TEXT NOT NULL REFERENCES tvs(tv_id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                windows_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                CHECK(start_date <= end_date));
                CREATE INDEX IF NOT EXISTS idx_schedule_exceptions_tv_dates
                    ON schedule_exceptions(tv_id,start_date,end_date);
            ''', EXCEPTIONS)
        current = {row[0] for row in self.db.execute('SELECT MigrationId FROM __EFMigrationsHistory')}
        if SESSIONS not in current:
            self._sql("""CREATE TABLE IF NOT EXISTS usage_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tv_id TEXT NOT NULL REFERENCES tvs(tv_id) ON DELETE CASCADE,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_seconds INTEGER NOT NULL DEFAULT 0 CHECK(duration_seconds >= 0));
                CREATE INDEX IF NOT EXISTS idx_usage_sessions_tv_start ON usage_sessions(tv_id,started_at);
            """, SESSIONS)
        current = {row[0] for row in self.db.execute('SELECT MigrationId FROM __EFMigrationsHistory')}
        if LOCKS not in current:
            self._sql("""CREATE TABLE IF NOT EXISTS tv_locks (
                tv_id TEXT PRIMARY KEY REFERENCES tvs(tv_id) ON DELETE CASCADE,
                mode TEXT NOT NULL CHECK(mode IN ('until_tomorrow','indefinite')),
                expires_at TEXT,
                created_at TEXT NOT NULL,
                CHECK((mode='indefinite' AND expires_at IS NULL) OR
                      (mode='until_tomorrow' AND expires_at IS NOT NULL)));
            """, LOCKS)
        self.db.execute('PRAGMA user_version=6')
        self.db.commit()

    def _exists(self, table):
        return self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone() is not None

    def _record(self, mid):
        self.db.execute('INSERT INTO __EFMigrationsHistory VALUES(?,?,?)',
            (mid,'SamsungTVControl/2.1',datetime.now(timezone.utc).isoformat()))
        self.db.commit()

    def _sql(self, sql, mid):
        stamp = datetime.now(timezone.utc).isoformat()
        script = ('BEGIN IMMEDIATE;\n' + sql + '\n'
                  + "INSERT INTO __EFMigrationsHistory VALUES ('"+mid+"','SamsungTVControl/2.1','"+stamp+"');\n"
                  + 'COMMIT;')
        try:
            self.db.executescript(script)
        except sqlite3.Error:
            if self.db.in_transaction:
                self.db.rollback()
            raise
