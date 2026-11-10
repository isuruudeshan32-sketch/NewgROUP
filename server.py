"""Linka Chat: dependency-free Python 3.11+ messaging server."""
import base64, hashlib, hmac, json, os, re, secrets, sqlite3, ssl, time, urllib.request, urllib.error
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlparse, parse_qs
from collections import defaultdict, deque
from threading import Lock
ROOT=Path(__file__).parent
DATA=Path(os.environ.get('DATA_DIR',ROOT/'data')); DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'linka.sqlite3'; PRODUCTION=os.environ.get('PRODUCTION')=='1'
LIMITS=defaultdict(deque); LOCK=Lock()
def db():
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
def init():
 with db() as c:
  c.executescript('''PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT UNIQUE NOT NULL,password TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user TEXT NOT NULL REFERENCES users(id),expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS contacts(owner TEXT NOT NULL REFERENCES users(id),other TEXT NOT NULL REFERENCES users(id),alias TEXT NOT NULL,PRIMARY KEY(owner,other));
CREATE TABLE IF NOT EXISTS rooms(id TEXT PRIMARY KEY,name TEXT NOT NULL,group_chat INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS members(room TEXT NOT NULL REFERENCES rooms(id),user TEXT NOT NULL REFERENCES users(id),PRIMARY KEY(room,user));
CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,room TEXT NOT NULL REFERENCES rooms(id),sender TEXT NOT NULL REFERENCES users(id),text TEXT NOT NULL,attachment TEXT,created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS message_room ON messages(room,created);
CREATE TABLE IF NOT EXISTS statuses(id TEXT PRIMARY KEY,user TEXT NOT NULL REFERENCES users(id),text TEXT NOT NULL,image TEXT,color TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS blocks(owner TEXT NOT NULL REFERENCES users(id),other TEXT NOT NULL REFERENCES users(id),PRIMARY KEY(owner,other));
''')
def phone(s):
 s=re.sub(r'[\s()\-]','',str(s))
 if not re.fullmatch(r'\+[1-9]\d{7,14}',s):raise ValueError('Use your full international phone number, e.g. +94771234567.')
 return s
def pw_hash(p,salt=None):
 salt=salt or secrets.token_hex(16)
 return salt+':'+hashlib.scrypt(p.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def pw_ok(p,h):
 try:return hmac.compare_digest(pw_hash(p,h.split(':')[0]),h)
 except Exception:return False
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def clean(s,n):
 if not isinstance(s,str) or not 0<len(s.strip())<=n:raise ValueError(f'Enter 1–{n} characters.')
 return s.strip()
def attachment(v):
 if v is None:return None
 if not isinstance(v,dict):raise ValueError('Invalid attachment')
 u=str(v.get('url',''));mime=u.split(';')[0].replace('data:','')
 if mime not in ['image/png','image/jpeg','image/webp','application/pdf','text/plain'] or ';base64,' not in u:raise ValueError('Unsupported attachment type.')
 try:raw=base64.b64decode(u.split(',',1)[1],validate=True)
 except Exception:raise ValueError('Invalid file data')
 if len(raw)>1000000:raise ValueError('Files must be under 1 MB.')
 if mime=='image/png' and not raw.startswith(b'\x89PNG'):raise ValueError('Invalid PNG')
 if mime=='image/jpeg' and not raw.startswith(b'\xff\xd8'):raise ValueError('Invalid JPEG')
 if mime=='image/webp' and not(raw[:4]==b'RIFF' and raw[8:12]==b'WEBP'):raise ValueError('Invalid WebP')
 if mime=='application/pdf' and not raw.startswith(b'%PDF'):raise ValueError('Invalid PDF')
 return {'url':u,'name':str(v.get('name','File'))[:120],'size':len(raw)}
class APIError(Exception):
 def __init__(self,status,msg):self.status=status;self.msg=msg
class Handler(BaseHTTPRequestHandler):
 server_version='Linka'
 def log_message(self,fmt,*args):pass
 def reply(self,obj,status=200,cookie=None):
  data=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.secure_headers()
  if cookie:self.send_header('Set-Cookie',cookie)
  self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def secure_headers(self):
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','same-origin');self.send_header('X-Frame-Options','DENY');self.send_header('Permissions-Policy','camera=(),microphone=(),geolocation=()')
  self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
  if PRODUCTION:self.send_header('Strict-Transport-Security','max-age=31536000')
 def limited(self,bucket,count,period=60):
  k=(bucket,self.client_address[0]);t=time.time()
  with LOCK:
   q=LIMITS[k]
   while q and q[0]<t-period:q.popleft()
   if len(q)>=count:raise APIError(429,'Too many requests. Please try again later.')
   q.append(t)
 def session(self,c):
  cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));token=cookie.get('linka_session')
  if not token:raise APIError(401,'Please sign in.')
  u=c.execute('SELECT users.* FROM users JOIN sessions ON users.id=sessions.user WHERE sessions.token=? AND sessions.expires>?',(digest(token.value),time.time())).fetchone()
  if not u:raise APIError(401,'Your session expired. Please sign in again.')
  return dict(u)
 def room(self,c,r,u):
  if not c.execute('SELECT 1 FROM members WHERE room=? AND user=?',(r,u)).fetchone():raise APIError(403,'You do not have access to this conversation.')
 def do_GET(self):self.handle_request()
 def do_POST(self):self.handle_request()
 def handle_request(self):
  path=urlparse(self.path).path
  try:
   if not path.startswith('/api/'):
    if self.command!='GET':raise APIError(405,'Method not allowed')
    files={'/':('index.html','text/html; charset=utf-8'),'/manifest.webmanifest':('manifest.webmanifest','application/manifest+json'),'/sw.js':('sw.js','text/javascript'),'/icon.svg':('icon.svg','image/svg+xml'),'/enhancements.js':('enhancements.js','text/javascript'),'/icon-192.png':('icon-192.png','image/png'),'/icon-512.png':('icon-512.png','image/png')}
    if path not in files:raise APIError(404,'Not found')
    f,m=files[path];data=(ROOT/'public'/f).read_bytes();self.send_response(200);self.send_header('Content-Type',m);self.send_header('Cache-Control','no-cache');self.secure_headers();self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
   self.limited('api',300)
   d={}
   if self.command=='POST':
    origin=self.headers.get('Origin');expected=os.environ.get('PUBLIC_ORIGIN','http://'+self.headers.get('Host',''))
    if PRODUCTION and not os.environ.get('PUBLIC_ORIGIN'):raise APIError(503,'Set PUBLIC_ORIGIN for production.')
    if origin!=expected:raise APIError(403,'Cross-origin requests are blocked.')
    if 'application/json' not in self.headers.get('Content-Type',''):raise APIError(415,'JSON required')
    n=int(self.headers.get('Content-Length','0'))
    if n<1 or n>1450000:raise APIError(413,'Request too large')
    d=json.loads(self.rfile.read(n))
    if not isinstance(d,dict):raise ValueError('Invalid JSON object')
   with db() as c:
    if path in ['/api/signup','/api/login'] and self.command=='POST':
     self.limited('auth',10,600);p=phone(d.get('phone',''));password=str(d.get('password',''))
     if path=='/api/signup':
      if len(password)<12 or len(password)>128:raise ValueError('Use a password with 12–128 characters.')
      name=clean(d.get('name',''),60);uid=secrets.token_hex(16)
      try:c.execute('INSERT INTO users VALUES(?,?,?,?,?)',(uid,name,p,pw_hash(password),time.time()))
      except sqlite3.IntegrityError:raise APIError(409,'Registration could not be completed. Try signing in or use another number.')
      u={'id':uid,'name':name,'phone':p}
     else:
      u=c.execute('SELECT * FROM users WHERE phone=?',(p,)).fetchone()
      # Equal-cost hash work even for unknown accounts.
      valid=pw_ok(password,u['password'] if u else pw_hash('dummy-check-password'))
      if not u or not valid:raise APIError(401,'Phone number or password is incorrect.')
      u=dict(u)
     token=secrets.token_urlsafe(32);c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),));c.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),u['id'],time.time()+604800));cookie='linka_session='+token+'; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800'+('; Secure' if PRODUCTION else '')
     self.reply({k:u[k] for k in ['id','name','phone']},cookie=cookie);return
    u=self.session(c);uid=u['id']
    if path=='/api/me':self.reply({k:u[k] for k in ['id','name','phone']});return
    if path=='/api/logout' and self.command=='POST':
     cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));c.execute('DELETE FROM sessions WHERE token=?',(digest(cookie['linka_session'].value),));self.reply({'ok':True},cookie='linka_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'+('; Secure' if PRODUCTION else ''));return
    if path=='/api/contacts':
     if self.command=='GET':self.reply({'contacts':[dict(r) for r in c.execute('SELECT users.id,users.name,users.phone,contacts.alias FROM contacts JOIN users ON users.id=contacts.other WHERE contacts.owner=?',(uid,))]});return
     p=phone(d.get('phone',''));other=c.execute('SELECT id,name FROM users WHERE phone=?',(p,)).fetchone()
     if not other:raise APIError(404,'This number has not registered with Linka yet.')
     if other['id']==uid:raise ValueError('That is your own number.')
     alias=clean(d.get('alias') or other['name'],60);c.execute('INSERT INTO contacts VALUES(?,?,?) ON CONFLICT(owner,other) DO UPDATE SET alias=excluded.alias',(uid,other['id'],alias));self.reply({'ok':True});return
    if path=='/api/block' and self.command=='POST':
     target=clean(d.get('user',''),64);c.execute('INSERT OR IGNORE INTO blocks VALUES(?,?)',(uid,target));self.reply({'ok':True});return
    if path=='/api/rooms':
     if self.command=='GET':
      result=[]
      for r in c.execute('SELECT rooms.* FROM rooms JOIN members ON rooms.id=members.room WHERE members.user=? ORDER BY created DESC',(uid,)).fetchall():
       r=dict(r);r['group']=bool(r.pop('group_chat'))
       if not r['group']:
        o=c.execute('SELECT users.id,users.name FROM members JOIN users ON users.id=members.user WHERE room=? AND user!=?',(r['id'],uid)).fetchone()
        if o:
         alias=c.execute('SELECT alias FROM contacts WHERE owner=? AND other=?',(uid,o['id'])).fetchone();r['name']=alias['alias'] if alias else o['name'];r['other']=o['id']
       r['messages']=[];last=c.execute('SELECT text,created,sender FROM messages WHERE room=? ORDER BY created DESC LIMIT 1',(r['id'],)).fetchone()
       if last:r['messages']=[{'text':last['text'],'time':time.strftime('%H:%M',time.localtime(last['created'])),'mine':last['sender']==uid}]
       result.append(r)
      self.reply({'rooms':result});return
     others=d.get('members',[])
     if not isinstance(others,list) or not 1<=len(others)<=30:raise ValueError('Choose 1–30 contacts.')
     ids=sorted(set([str(i) for i in others if i!=uid]));group=bool(d.get('group'))
     if not group and len(ids)!=1:raise ValueError('Direct chats need one contact.')
     for other in ids:
      if not c.execute('SELECT 1 FROM contacts WHERE owner=? AND other=?',(uid,other)).fetchone():raise APIError(403,'Save each contact before creating a conversation.')
      if c.execute('SELECT 1 FROM blocks WHERE (owner=? AND other=?) OR (owner=? AND other=?)',(uid,other,other,uid)).fetchone():raise APIError(403,'Messaging is unavailable for this contact.')
     if not group:
      existing=c.execute('SELECT rooms.id FROM rooms JOIN members a ON a.room=rooms.id JOIN members b ON b.room=rooms.id WHERE group_chat=0 AND a.user=? AND b.user=?',(uid,ids[0])).fetchone()
      if existing:self.reply({'id':existing['id']});return
     rid=secrets.token_hex(16);c.execute('INSERT INTO rooms VALUES(?,?,?,?)',(rid,clean(d.get('name') or 'Conversation',60),int(group),time.time()));c.executemany('INSERT INTO members VALUES(?,?)',[(rid,i) for i in [uid]+ids]);self.reply({'id':rid});return
    if path=='/api/messages':
     rid=d.get('room') if self.command=='POST' else parse_qs(urlparse(self.path).query).get('room',[''])[0];self.room(c,rid,uid)
     if self.command=='GET':
      rows=c.execute('SELECT messages.*,users.name AS sender_name FROM messages JOIN users ON messages.sender=users.id WHERE room=? ORDER BY created DESC LIMIT 200',(rid,)).fetchall();self.reply({'room':rid,'messages':[{'id':r['id'],'user':r['sender'],'sender':r['sender_name'],'text':r['text'],'at':r['created']*1000,'file':json.loads(r['attachment']) if r['attachment'] else None} for r in reversed(rows)]});return
     self.limited('messages',60);blocked=c.execute('SELECT 1 FROM blocks JOIN members ON members.user=blocks.owner WHERE members.room=? AND blocks.other=?',(rid,uid)).fetchone()
     if blocked:raise APIError(403,'Messaging is unavailable in this conversation.')
     text=str(d.get('text','')).strip();f=attachment(d.get('file'))
     if len(text)>4000 or (not text and not f):raise ValueError('Enter a message up to 4,000 characters or attach a file.')
     c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?)',(secrets.token_hex(16),rid,uid,text,json.dumps(f) if f else None,time.time()));self.reply({'ok':True});return
    if path=='/api/statuses':
     c.execute('DELETE FROM statuses WHERE created<?',(time.time()-86400,))
     if self.command=='GET':
      rows=c.execute('SELECT statuses.*,users.name FROM statuses JOIN users ON users.id=statuses.user WHERE (statuses.user=? OR (statuses.user IN (SELECT other FROM contacts WHERE owner=?) AND statuses.user IN (SELECT owner FROM contacts WHERE other=?))) AND NOT EXISTS (SELECT 1 FROM blocks WHERE (blocks.owner=? AND blocks.other=statuses.user) OR (blocks.other=? AND blocks.owner=statuses.user)) ORDER BY created DESC',(uid,uid,uid,uid,uid)).fetchall();self.reply({'statuses':[dict(r) for r in rows]});return
     self.limited('status',15);t=str(d.get('text','')).strip();f=attachment(d.get('image'));color=d.get('color','#244f38')
     if len(t)>500 or (not t and not f):raise ValueError('Add text or a photo.')
     if f and not f['url'].startswith('data:image/'):raise ValueError('Statuses support images only.')
     if not re.fullmatch('#[0-9a-fA-F]{6}',color):raise ValueError('Invalid color')
     c.execute('INSERT INTO statuses VALUES(?,?,?,?,?,?)',(secrets.token_hex(16),uid,t,f['url'] if f else None,color,time.time()));self.reply({'ok':True});return
    if path=='/api/status/delete' and self.command=='POST':c.execute('DELETE FROM statuses WHERE id=? AND user=?',(d.get('id'),uid));self.reply({'ok':True});return
    if path=='/api/ai' and self.command=='POST':
     self.limited('ai',10,600);q=clean(d.get('text',''),2000);key=os.environ.get('OPENAI_API_KEY')
     if not key:self.reply({'text':'AI is not configured yet. Ask the app owner to set OPENAI_API_KEY on the server. Your message has not been sent to an AI provider.','configured':False});return
     if d.get('consent') is not True:raise ValueError('Confirm that you want to send this prompt to the AI provider.')
     payload={'model':os.environ.get('OPENAI_MODEL','gpt-4.1-mini'),'messages':[{'role':'system','content':'You are Linka Assistant. Be concise, helpful, and respond in the language the user uses. You cannot read their private chats or contacts.'},{'role':'user','content':q}],'max_tokens':600}
     request=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
     try:
      with urllib.request.urlopen(request,timeout=30,context=ssl.create_default_context()) as resp:answer=json.load(resp)['choices'][0]['message']['content']
     except Exception:raise APIError(502,'AI service is unavailable. Check the server configuration and try again.')
     self.reply({'text':answer,'configured':True});return
    raise APIError(404,'Not found')
  except APIError as e:self.reply({'error':e.msg},e.status)
  except (ValueError,TypeError,KeyError,json.JSONDecodeError):self.reply({'error':'Invalid input. Check the phone number, password, text length and attachment format.'},400)
  except Exception:self.reply({'error':'Server error. Please try again.'},500)
if __name__=='__main__':
 init();port=int(os.environ.get('PORT','8080'));print(f'Linka Chat: http://localhost:{port}',flush=True);ThreadingHTTPServer((os.environ.get('HOST','0.0.0.0'),port),Handler).serve_forever()
