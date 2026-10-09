"""Same-origin HTTP API + static SPA; cookie session, CSRF, and role permissions."""
import json
import logging
import mimetypes
import os
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from app.managers.auth_manager import AuthError
from app.models.schemas import ValidationError

class HttpApi:
    def __init__(self, facade, settings, data, auth, static_root=None):
        self.facade,self.settings,self.data,self.auth=facade,settings,data,auth
        self.static_root=Path(static_root).resolve() if static_root else None

    def serve(self, host='127.0.0.1', port=8765):
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def reply(self, value, code=200, extra=None):
                raw=json.dumps(value,ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
                for k,v in (extra or {}).items():self.send_header(k,v)
                self.end_headers();self.wfile.write(raw)

            def cookie_token(self):
                jar=cookies.SimpleCookie()
                try:jar.load(self.headers.get('Cookie',''))
                except cookies.CookieError:return None
                return jar['stc_session'].value if 'stc_session' in jar else None

            def cookie_header(self,token='',max_age=None):
                secure='; Secure' if os.getenv('STC_SECURE_COOKIE')=='1' else ''
                return f'stc_session={token}; Path=/; HttpOnly; SameSite=Strict{secure}'+(f'; Max-Age={max_age}' if max_age is not None else '')

            def body_json(self):
                length=int(self.headers.get('Content-Length','0'))
                if not 1 <= length <= 32768:raise ValidationError('Body 1..32768 Bytes erforderlich')
                return json.loads(self.rfile.read(length))

            def files(self,path):
                root=outer.static_root
                if root is None or not (root/'index.html').is_file():
                    self.reply({'error':'Frontend nicht gebaut; siehe README'},404);return
                # SPA routes only; never serve dotfiles or traversal paths.
                rel=path.lstrip('/')
                if '..' in Path(rel).parts or any(x.startswith('.') for x in Path(rel).parts):
                    self.reply({'error':'Nicht gefunden'},404);return
                file=(root/rel).resolve() if rel else root/'index.html'
                if not file.is_relative_to(root) or not file.is_file():file=root/'index.html'
                data=file.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type',mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
                self.send_header('Content-Length',str(len(data)))
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Cache-Control','no-store' if file.name=='index.html' else 'public, max-age=3600')
                self.end_headers();self.wfile.write(data)

            def handle_api(self,method,path,query):
                origin=self.headers.get('Origin')
                if method!='GET' and origin:
                    from urllib.parse import urlsplit as parse_origin
                    origin_parts=parse_origin(origin)
                    allowed_dev=(self.client_address[0] in ('127.0.0.1','::1') and origin_parts.netloc in ('127.0.0.1:5173','localhost:5173') and origin_parts.scheme=='http')
                    if (origin_parts.netloc != self.headers.get('Host') or origin_parts.scheme not in ('http','https')) and not allowed_dev:
                        raise AuthError('Ungültiger Origin',403)
                parts=path.strip('/').split('/')
                body=self.body_json() if method in ('POST','PUT','PATCH') else None
                if path=='/api/auth/setup-status' and method=='GET':
                    return self.reply({'needs_setup':outer.data.user_count()==0})
                if path=='/api/auth/setup' and method=='POST':
                    # Local-only bootstrap even if service is later LAN-bound.
                    if self.client_address[0] not in ('127.0.0.1','::1'):
                        raise AuthError('Ersteinrichtung nur lokal auf dem Server',403)
                    if outer.data.user_count()!=0:raise AuthError('Bereits eingerichtet',409)
                    return self.reply(outer.auth.create(body,bootstrap=True),201)
                if path=='/api/auth/login' and method=='POST':
                    token,csrf,user=outer.auth.login(body)
                    return self.reply({'user':user,'csrf_token':csrf},extra={'Set-Cookie':self.cookie_header(token,8*3600)})
                token=self.cookie_token()
                user=outer.auth.current(token)
                if method!='GET':outer.auth.verify_csrf(user,self.headers.get('X-CSRF-Token',''))
                if path=='/api/auth/me' and method=='GET':
                    return self.reply({'user':{k:user[k] for k in ('id','username','display_name','role')},'csrf_token':outer.auth.new_csrf(token)})
                if path=='/api/auth/logout' and method=='POST':
                    outer.auth.logout(token)
                    return self.reply({'ok':True},extra={'Set-Cookie':self.cookie_header('',0)})
                if path=='/api/users' and method=='GET':
                    outer.auth.require(user,'users');return self.reply(outer.data.list_users())
                if path=='/api/users' and method=='POST':
                    outer.auth.require(user,'users');return self.reply(outer.auth.create(body),201)
                if len(parts)==3 and parts[:2]==['api','users'] and method=='PATCH':
                    outer.auth.require(user,'users')
                    if not isinstance(body,dict) or not set(body).issubset({'role','active'}) or not body:
                        raise ValidationError('role und/oder active erwartet')
                    role=body.get('role');active=body.get('active')
                    if role is not None and role not in ('admin','manager','viewer'):raise ValidationError('Rolle ungültig')
                    if active is not None and type(active) is not bool:raise ValidationError('active muss bool sein')
                    outer.data.modify_user(int(parts[2]),role,active)
                    return self.reply({'ok':True})
                outer.auth.require(user,'read')
                if path=='/api/tvs' and method=='GET':return self.reply(outer.facade.get_tvs())
                if len(parts)==4 and parts[:2]==['api','tvs'] and parts[3]=='exceptions':
                    if method=='GET':return self.reply(outer.facade.get_exceptions(parts[2]))
                    if method=='POST':
                        outer.auth.require(user,'config')
                        return self.reply(outer.facade.create_exception(parts[2],body),201)
                if len(parts)==5 and parts[:2]==['api','tvs'] and parts[3]=='exceptions' and method=='DELETE':
                    outer.auth.require(user,'config')
                    return self.reply(outer.facade.delete_exception(parts[2],int(parts[4])))
                if len(parts)==4 and parts[:2]==['api','tvs'] and parts[3]=='statistics' and method=='GET':
                    return self.reply(outer.facade.get_statistics(parts[2]))
                if len(parts)==4 and parts[:2]==['api','tvs'] and parts[3]=='lock':
                    if method=='GET':return self.reply({'lock':outer.facade.get_lock(parts[2])})
                    outer.auth.require(user,'control')
                    if method=='POST':
                        if not isinstance(body,dict) or set(body)!={'mode'}:
                            raise ValidationError('mode erforderlich')
                        return self.reply({'lock':outer.facade.set_lock(parts[2],body['mode'])})
                    if method=='DELETE':return self.reply(outer.facade.clear_lock(parts[2]))
                if len(parts)==4 and parts[:2]==['api','tvs']:
                    tv_id=parts[2]
                    if parts[3]=='status' and method=='GET':return self.reply(outer.facade.get_status(tv_id))
                    if parts[3]=='events' and method=='GET':
                        limit=int(parse_qs(query).get('limit',['100'])[0]);return self.reply(outer.facade.get_events(tv_id,limit))
                    if parts[3]=='bonus' and method=='POST':
                        outer.auth.require(user,'control')
                        if not isinstance(body,dict) or set(body)!={'minutes','expires_at'}:
                            raise ValidationError('minutes und expires_at erforderlich')
                        return self.reply(outer.facade.add_bonus(tv_id,body['minutes'],body['expires_at']))
                if len(parts)==3 and parts[:2]==['api','tvs'] and method=='DELETE':
                    outer.auth.require(user,'users')
                    return self.reply(outer.facade.delete_tv(parts[2]))
                if path=='/api/tvs' and method=='POST':
                    outer.auth.require(user,'users')
                    if not isinstance(body,dict):raise ValidationError('TV-Konfiguration erwartet')
                    if outer.facade.tvs.get(body.get('tv_id')) is not None:
                        raise ValidationError('TV-ID existiert bereits')
                    return self.reply(outer.facade.put_tv(body),201)
                if len(parts)==3 and parts[:2]==['api','tvs'] and method=='PUT':
                    outer.auth.require(user,'config')
                    if not isinstance(body,dict) or body.get('tv_id')!=parts[2]:raise ValidationError('TV-ID stimmt nicht überein')
                    return self.reply(outer.facade.put_tv(body))
                if path=='/api/settings' and method=='GET':return self.reply(outer.settings.get())
                if path=='/api/settings' and method=='PUT':
                    outer.auth.require(user,'config');return self.reply(outer.settings.update(body))
                if path=='/api/migrations' and method=='GET':
                    outer.auth.require(user,'users');return self.reply(outer.data.migration_history())
                return self.reply({'error':'Nicht gefunden'},404)

            def dispatch(self, method):
                try:
                    url=urlsplit(self.path)
                    if url.path.startswith('/api/'):
                        return self.handle_api(method,url.path,url.query)
                    if method=='GET':return self.files(url.path)
                    return self.reply({'error':'Nicht gefunden'},404)
                except AuthError as exc:self.reply({'error':str(exc)},exc.status)
                except (ValidationError,KeyError,TypeError,ValueError,OverflowError,json.JSONDecodeError) as exc:
                    self.reply({'error':str(exc)},400)
                except Exception:
                    logging.exception('HTTP API Fehler');self.reply({'error':'Interner Fehler'},500)

            def do_GET(self):self.dispatch('GET')
            def do_POST(self):self.dispatch('POST')
            def do_PUT(self):self.dispatch('PUT')
            def do_PATCH(self):self.dispatch('PATCH')
            def do_DELETE(self):self.dispatch('DELETE')
        server=ThreadingHTTPServer((host,port),Handler)
        try:server.serve_forever()
        finally:server.server_close()
