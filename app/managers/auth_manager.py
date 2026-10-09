"""Authentication and permission policy; persistence lives exclusively in Data."""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

ROLES = {'admin': {'read','control','config','users'},
         'manager': {'read','control','config'},
         'viewer': {'read'}}

class AuthError(Exception):
    def __init__(self, message='Anmeldung fehlgeschlagen', status=401):
        super().__init__(message)
        self.status=status

class AuthManager:
    def __init__(self, data):
        self.data=data

    @staticmethod
    def now():
        return datetime.now(timezone.utc)

    @staticmethod
    def hashed(value, salt):
        return hashlib.pbkdf2_hmac('sha256',value.encode(),bytes.fromhex(salt),600_000).hex()

    @staticmethod
    def validate_credential(kind, value):
        if kind=='pin' and isinstance(value,str) and re.fullmatch(r'\d{6,12}',value):
            return
        if kind=='pattern' and isinstance(value,str) and re.fullmatch(r'[1-9]{6,9}',value) and len(set(value))==len(value):
            return
        raise AuthError('PIN: 6–12 Ziffern; Muster: 6–9 unterschiedliche Punkte',400)

    @staticmethod
    def validate_identity(name, display, role):
        if not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{3,32}',name):
            raise AuthError('Benutzername 3–32 Zeichen (a-z, 0-9, _,-)',400)
        if not isinstance(display,str) or not 1<=len(display.strip())<=60:
            raise AuthError('Anzeigename erforderlich',400)
        if role not in ROLES:
            raise AuthError('Ungültige Rolle',400)

    def create(self, payload, bootstrap=False):
        if not isinstance(payload,dict):
            raise AuthError('JSON-Objekt erwartet',400)
        name=payload.get('username');display=payload.get('display_name');role='admin' if bootstrap else payload.get('role')
        kind=payload.get('credential_type');value=payload.get('credential')
        self.validate_identity(name,display,role)
        self.validate_credential(kind,value)
        salt=secrets.token_hex(24)
        try:
            uid=self.data.create_user(name,display.strip(),role,kind,self.hashed(value,salt),salt,self.now().isoformat(),bootstrap)
        except Exception as exc:
            raise AuthError('Benutzer existiert bereits oder Einrichtung abgeschlossen',409) from exc
        return {'id':uid,'username':name,'display_name':display.strip(),'role':role,'credential_type':kind,'active':True}

    def login(self, payload):
        if not isinstance(payload,dict):
            raise AuthError()
        name=payload.get('username');value=payload.get('credential')
        if not isinstance(name,str) or not isinstance(value,str) or len(value)>100:
            raise AuthError()
        user=self.data.user_by_name(name)
        # Ensure unknown usernames still execute a slow hash.
        if not user:
            self.hashed(value,'00'*24)
            raise AuthError()
        now=self.now()
        if user['locked_until'] and datetime.fromisoformat(user['locked_until'])>now:
            raise AuthError('Zu viele Versuche. Bitte später erneut versuchen.',429)
        valid=hmac.compare_digest(self.hashed(value,user['salt']),user['secret_hash'])
        if not valid or not user['active']:
            attempts=user['failed_attempts']+1
            # Lock on every fifth failed attempt; persistent across server restarts.
            until=(now+timedelta(minutes=15)).isoformat() if attempts>=5 else None
            self.data.login_failure(user['id'],0 if until else attempts,until)
            raise AuthError()
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        expires=(now+timedelta(hours=8)).isoformat()
        self.data.login_success(user['id'],hashlib.sha256(token.encode()).hexdigest(),hashlib.sha256(csrf.encode()).hexdigest(),expires,now.isoformat())
        return token,csrf,{'id':user['id'],'username':user['username'],'display_name':user['display_name'],'role':user['role']}

    def current(self, token):
        if not token:
            raise AuthError()
        user=self.data.find_session(hashlib.sha256(token.encode()).hexdigest(),self.now().isoformat())
        if not user or not user['active']:
            raise AuthError()
        return user

    def new_csrf(self, token):
        csrf=secrets.token_urlsafe(32)
        self.data.rotate_csrf(hashlib.sha256(token.encode()).hexdigest(),hashlib.sha256(csrf.encode()).hexdigest())
        return csrf

    def verify_csrf(self, user, value):
        if not value or not hmac.compare_digest(user['csrf_hash'],hashlib.sha256(value.encode()).hexdigest()):
            raise AuthError('CSRF-Prüfung fehlgeschlagen',403)

    def require(self, user, permission):
        if permission not in ROLES.get(user['role'],set()):
            raise AuthError('Keine Berechtigung',403)

    def logout(self, token):
        if token:
            self.data.delete_session(hashlib.sha256(token.encode()).hexdigest())
