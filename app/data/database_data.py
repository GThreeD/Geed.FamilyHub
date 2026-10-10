from __future__ import annotations
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.data.migrations.migration_manager import MigrationManager

class DatabaseData:
    """Only this layer opens connections or issues SQL; no SQL in managers/services."""
    def __init__(self, path: Path):
        raw = Path(path).expanduser()
        if raw.is_symlink():
            raise ValueError('Symlink-DB nicht erlaubt')
        self.path = raw.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.exists() and self.path.is_symlink():
            raise ValueError('Symlink-DB nicht erlaubt')
        self.path.touch(exist_ok=True, mode=0o600)
        os.chmod(self.path, 0o600)
        self.migrate()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=10000')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def migrate(self):
        with self.connection() as db:
            MigrationManager(db).apply()

    def migration_history(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute('SELECT * FROM __EFMigrationsHistory ORDER BY MigrationId')]

    def get_settings(self):
        with self.connection() as db:
            return dict(db.execute('SELECT * FROM app_settings WHERE id=1').fetchone())

    def save_settings(self, values):
        with self.connection() as db:
            db.execute('UPDATE app_settings SET poll_seconds=?,confirm_online_checks=?,confirm_offline_checks=?,cooldown_seconds=?,power_hold_seconds=?,armed=? WHERE id=1',
                (values['poll_seconds'],values['confirm_online_checks'],values['confirm_offline_checks'],
                 values['cooldown_seconds'],values['power_hold_seconds'],int(values['armed'])))

    def initial_import(self, tv_configs, runtime):
        import json
        with self.connection() as db:
            if db.execute('SELECT 1 FROM tvs LIMIT 1').fetchone():
                return False
            for tv in tv_configs:
                db.execute('INSERT INTO tvs VALUES (?,?,?,?,?,?,?,?)',
                    (tv.tv_id,tv.name,tv.ip,int(tv.enabled),tv.timezone,
                     tv.daily_limit_minutes,tv.weekly_limit_minutes,json.dumps(tv.schedule)))
            db.execute('UPDATE app_settings SET poll_seconds=?,confirm_online_checks=?,confirm_offline_checks=?,cooldown_seconds=?,power_hold_seconds=? WHERE id=1',
                (runtime.poll_seconds,runtime.confirm_online_checks,runtime.confirm_offline_checks,
                 runtime.cooldown_seconds,runtime.power_hold_seconds))
            return True

    def upsert_tv(self, tv, schedule_json: str):
        with self.connection() as db:
            db.execute('''INSERT INTO tvs VALUES(?,?,?,?,?,?,?,?)
             ON CONFLICT(tv_id) DO UPDATE SET name=excluded.name,ip=excluded.ip,enabled=excluded.enabled,
             timezone=excluded.timezone,daily_limit_minutes=excluded.daily_limit_minutes,
             weekly_limit_minutes=excluded.weekly_limit_minutes,schedule_json=excluded.schedule_json''',
             (tv.tv_id,tv.name,tv.ip,int(tv.enabled),tv.timezone,tv.daily_limit_minutes,tv.weekly_limit_minutes,schedule_json))

    def list_tvs(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute('SELECT * FROM tvs ORDER BY tv_id')]

    def usage_totals(self, tv_id, day, week):
        with self.connection() as db:
            rows = db.execute('''SELECT period_type,seconds FROM usage WHERE tv_id=? AND
              ((period_type='day' AND period_key=?) OR (period_type='week' AND period_key=?))''', (tv_id,day,week))
            out = {'day':0,'week':0}
            for row in rows:
                out[row['period_type']] = row['seconds']
            return out

    def available_bonus(self, tv_id, at):
        with self.connection() as db:
            val = db.execute('''SELECT COALESCE(SUM(granted_seconds-consumed_seconds),0) FROM bonus
             WHERE tv_id=? AND expires_at>?''',(tv_id, at)).fetchone()[0]
            return int(val)

    def grant_bonus(self, tv_id, seconds, expires_at, created_at):
        with self.connection() as db:
            db.execute('INSERT INTO bonus(tv_id,granted_seconds,expires_at,created_at) VALUES(?,?,?,?)',
                       (tv_id,seconds,expires_at,created_at))

    def list_bonus_grants(self, tv_id):
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,granted_seconds,consumed_seconds,expires_at,created_at "
                "FROM bonus WHERE tv_id=? ORDER BY id DESC LIMIT 100", (tv_id,))]

    def revoke_bonus_grant(self, tv_id, grant_id):
        with self.connection() as db:
            row = db.execute("SELECT consumed_seconds,granted_seconds FROM bonus WHERE tv_id=? AND id=?", (tv_id,grant_id)).fetchone()
            if row is None or row['consumed_seconds'] == row['granted_seconds']:
                return False
            if row['consumed_seconds'] == 0:
                db.execute("DELETE FROM bonus WHERE tv_id=? AND id=?",(tv_id,grant_id))
            else:
                db.execute("UPDATE bonus SET granted_seconds=consumed_seconds WHERE tv_id=? AND id=?",(tv_id,grant_id))
            return True

    def record_usage(self, tv_id, day, week, seconds, bonus_seconds, at):
        """Atomic usage + bonus consumption; never consume more bonus than remains."""
        if seconds <= 0:
            return
        with self.connection() as db:
            for kind,key in (('day',day),('week',week)):
                db.execute('''INSERT INTO usage(tv_id,period_type,period_key,seconds) VALUES(?,?,?,?)
                ON CONFLICT(tv_id,period_type,period_key) DO UPDATE SET seconds=seconds+excluded.seconds''',
                (tv_id,kind,key,seconds))
            remaining = bonus_seconds
            if remaining:
                entries = db.execute('''SELECT id,granted_seconds-consumed_seconds AS available FROM bonus
                    WHERE tv_id=? AND expires_at>? AND consumed_seconds<granted_seconds
                    ORDER BY expires_at,id''',(tv_id,at)).fetchall()
                # A grant can run out or be revoked between polls. Still record
                # observed usage and let enforcement proceed when credit reaches zero.
                remaining = min(remaining, sum(e['available'] for e in entries))
                for entry in entries:
                    take = min(remaining,entry['available'])
                    if take:
                        db.execute('UPDATE bonus SET consumed_seconds=consumed_seconds+? WHERE id=?',(take,entry['id']))
                        remaining -= take
                    if not remaining:
                        break

    def log_event(self, tv_id, at, kind, details):
        with self.connection() as db:
            db.execute('INSERT INTO events(tv_id,timestamp,kind,details) VALUES(?,?,?,?)', (tv_id,at,kind,details[:500]))

    def events(self, tv_id, limit=100):
        with self.connection() as db:
            return [dict(r) for r in db.execute('SELECT timestamp,kind,details FROM events WHERE tv_id=? ORDER BY id DESC LIMIT ?', (tv_id,limit))]

    def runtime_state(self, tv_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM runtime WHERE tv_id=?',(tv_id,)).fetchone()
            return dict(row) if row else {'last_attempt_at': None,'blocked_until_offline':0}

    def set_runtime(self, tv_id, last_attempt_at, blocked_until_offline):
        with self.connection() as db:
            db.execute('''INSERT INTO runtime VALUES(?,?,?) ON CONFLICT(tv_id) DO UPDATE
             SET last_attempt_at=excluded.last_attempt_at,blocked_until_offline=excluded.blocked_until_offline''',
             (tv_id,last_attempt_at,int(blocked_until_offline)))

    # Auth persistence. Keep SQL in Data, business policy in AuthManager.
    def user_count(self):
        with self.connection() as db:
            return db.execute('SELECT COUNT(*) FROM users').fetchone()[0]

    def list_users(self):
        with self.connection() as db:
            return [dict(r) for r in db.execute('SELECT id,username,display_name,role,credential_type,active,created_at FROM users ORDER BY id')]

    def user_by_name(self, name):
        with self.connection() as db:
            row=db.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE',(name,)).fetchone()
            return dict(row) if row else None

    def user_by_id(self, uid):
        with self.connection() as db:
            row=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            return dict(row) if row else None

    def create_user(self, name, display, role, kind, digest, salt, now, bootstrap=False):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if bootstrap and db.execute('SELECT COUNT(*) FROM users').fetchone()[0] != 0:
                raise ValueError('Einrichtung bereits abgeschlossen')
            db.execute('INSERT INTO users(username,display_name,role,credential_type,secret_hash,salt,created_at) VALUES(?,?,?,?,?,?,?)',
                       (name,display,role,kind,digest,salt,now))
            return db.execute('SELECT last_insert_rowid()').fetchone()[0]

    def login_failure(self, uid, attempts, until):
        with self.connection() as db:
            db.execute('UPDATE users SET failed_attempts=?,locked_until=? WHERE id=?',(attempts,until,uid))

    def login_success(self, uid, session_hash, csrf_hash, expires, now):
        with self.connection() as db:
            db.execute('UPDATE users SET failed_attempts=0,locked_until=NULL WHERE id=?',(uid,))
            db.execute('DELETE FROM auth_sessions WHERE user_id=?',(uid,))
            db.execute('INSERT INTO auth_sessions VALUES(?,?,?,?,?)',(session_hash,uid,csrf_hash,expires,now))

    def find_session(self, session_hash, now):
        with self.connection() as db:
            row=db.execute("""SELECT s.csrf_hash,s.expires_at,u.id,u.username,u.display_name,u.role,u.active
                              FROM auth_sessions s JOIN users u ON u.id=s.user_id
                              WHERE s.id_hash=? AND s.expires_at>?""",(session_hash,now)).fetchone()
            return dict(row) if row else None

    def delete_session(self, session_hash):
        with self.connection() as db:
            db.execute('DELETE FROM auth_sessions WHERE id_hash=?',(session_hash,))

    def modify_user(self, uid, role=None, active=None):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT id,role,active FROM users WHERE id=?',(uid,)).fetchone()
            if not row:
                raise ValueError('Benutzer nicht gefunden')
            if row['role']=='admin' and row['active'] and (role not in (None,'admin') or active is False):
                other=db.execute('SELECT COUNT(*) FROM users WHERE role=? AND active=1 AND id<>?',('admin',uid)).fetchone()[0]
                if other==0:
                    raise ValueError('Letzter aktiver Admin darf nicht entfernt werden')
            db.execute('UPDATE users SET role=?,active=? WHERE id=?',
                       (role if role is not None else row['role'],int(active) if active is not None else row['active'],uid))
            db.execute('DELETE FROM auth_sessions WHERE user_id=?',(uid,))

    def rotate_csrf(self, session_hash, csrf_hash):
        with self.connection() as db:
            db.execute('UPDATE auth_sessions SET csrf_hash=? WHERE id_hash=?',(csrf_hash,session_hash))

    def list_schedule_exceptions(self, tv_id):
        with self.connection() as db:
            return [dict(r) for r in db.execute(
                'SELECT id,tv_id,name,start_date,end_date,windows_json FROM schedule_exceptions WHERE tv_id=? ORDER BY start_date,id',
                (tv_id,))]

    def schedule_exception_for_date(self, tv_id, local_date):
        with self.connection() as db:
            row = db.execute('''SELECT id,tv_id,name,start_date,end_date,windows_json
                FROM schedule_exceptions WHERE tv_id=? AND start_date<=? AND end_date>=?
                ORDER BY start_date DESC,id DESC LIMIT 1''', (tv_id,local_date,local_date)).fetchone()
            return dict(row) if row else None

    def create_schedule_exception(self, tv_id, name, start_date, end_date, windows_json, created_at):
        with self.connection() as db:
            existing = db.execute('''SELECT 1 FROM schedule_exceptions WHERE tv_id=? AND start_date<=? AND end_date>=?''',
                                  (tv_id,end_date,start_date)).fetchone()
            if existing:
                raise ValueError('Zeitraum überschneidet sich mit einer bestehenden Ausnahme')
            cursor = db.execute('''INSERT INTO schedule_exceptions
                (tv_id,name,start_date,end_date,windows_json,created_at) VALUES (?,?,?,?,?,?)''',
                (tv_id,name,start_date,end_date,windows_json,created_at))
            return cursor.lastrowid

    def remove_schedule_exception(self, tv_id, exception_id):
        with self.connection() as db:
            return db.execute('DELETE FROM schedule_exceptions WHERE tv_id=? AND id=?',
                              (tv_id,exception_id)).rowcount > 0

    # Device management
    def delete_tv(self, tv_id):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM tvs WHERE tv_id=?', (tv_id,)).fetchone():
                return False
            db.execute('DELETE FROM events WHERE tv_id=?', (tv_id,))
            db.execute('DELETE FROM tvs WHERE tv_id=?', (tv_id,))
            return True

    # Observed sessions are not inferred from scheduled allowance.
    def start_usage_session(self, tv_id, at):
        with self.connection() as db:
            db.execute("""INSERT INTO usage_sessions(tv_id,started_at)
                SELECT ?,? WHERE NOT EXISTS
                (SELECT 1 FROM usage_sessions WHERE tv_id=? AND ended_at IS NULL)""",
                (tv_id,at,tv_id))

    def end_usage_session(self, tv_id, at):
        with self.connection() as db:
            db.execute("""UPDATE usage_sessions SET ended_at=? WHERE tv_id=? AND ended_at IS NULL""",(at,tv_id))

    def add_session_duration(self, tv_id, seconds):
        if seconds <= 0:
            return
        with self.connection() as db:
            db.execute("""UPDATE usage_sessions SET duration_seconds=duration_seconds+?
                WHERE tv_id=? AND ended_at IS NULL""",(seconds,tv_id))

    def usage_statistics(self, tv_id, limit=30):
        with self.connection() as db:
            days=[dict(r) for r in db.execute("""SELECT period_key AS day, seconds FROM usage
                WHERE tv_id=? AND period_type='day' ORDER BY period_key DESC LIMIT ?""",(tv_id,limit))]
            sessions=[dict(r) for r in db.execute("""SELECT id,started_at,ended_at,duration_seconds
                FROM usage_sessions WHERE tv_id=? ORDER BY id DESC LIMIT 100""",(tv_id,))]
            return {'days':days,'sessions':sessions,'session_count':len(sessions)}

    # A lock is persisted; expiry is interpreted in UTC by the manager.
    def get_tv_lock(self,tv_id):
        with self.connection() as db:
            r=db.execute('SELECT * FROM tv_locks WHERE tv_id=?',(tv_id,)).fetchone()
            return dict(r) if r else None

    def save_tv_lock(self,tv_id,mode,expires_at,created_at):
        with self.connection() as db:
            db.execute("""INSERT INTO tv_locks(tv_id,mode,expires_at,created_at) VALUES(?,?,?,?)
                ON CONFLICT(tv_id) DO UPDATE SET mode=excluded.mode,
                expires_at=excluded.expires_at,created_at=excluded.created_at""",
                (tv_id,mode,expires_at,created_at))

    def remove_tv_lock(self,tv_id):
        with self.connection() as db:
            db.execute('DELETE FROM tv_locks WHERE tv_id=?',(tv_id,))
