import unittest, tempfile, threading, json, urllib.request, urllib.error, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
class ChatTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();server.DB=Path(cls.tmp.name)/'test.db';server.init()
  cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.base='http://127.0.0.1:'+str(cls.http.server_port)
  threading.Thread(target=cls.http.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
 def req(self,path,data=None,cookie=None,origin=None):
  headers={}
  if cookie:headers['Cookie']=cookie
  if data is not None:headers.update({'Content-Type':'application/json','Origin':origin or self.base})
  req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
  try:r=urllib.request.urlopen(req)
  except urllib.error.HTTPError as e:r=e
  raw=r.read();return r.status,json.loads(raw) if r.headers.get('Content-Type','').startswith('application/json') else raw,r.headers
 def test_complete_messaging_and_privacy_flow(self):
  self.assertEqual(self.req('/api/rooms')[0],401)
  a=self.req('/api/signup',{'name':'Alice','phone':'+94771111111','password':'Alice-password-123'})
  self.assertEqual(a[0],200);ac=a[2]['Set-Cookie'].split(';')[0];aid=a[1]['id'];self.assertIn('HttpOnly',a[2]['Set-Cookie'])
  b=self.req('/api/signup',{'name':'Bob','phone':'+94772222222','password':'Bob-password-123'})
  bc=b[2]['Set-Cookie'].split(';')[0];bid=b[1]['id']
  self.assertEqual(self.req('/api/login',{'phone':'+94771111111','password':'wrong'})[0],401)
  self.assertEqual(self.req('/api/contacts',{'phone':'+94772222222'},ac,origin='https://evil.example')[0],403)
  self.assertEqual(self.req('/api/contacts',{'phone':'+94772222222','alias':'My friend'},ac)[0],200)
  room=self.req('/api/rooms',{'members':[bid],'name':'Direct','group':False},ac)[1]['id']
  self.assertEqual(self.req('/api/messages',{'room':room,'text':'Hello Bob!'},ac)[0],200)
  self.assertEqual(self.req('/api/messages?room='+room,cookie=bc)[1]['messages'][0]['text'],'Hello Bob!')
  self.assertEqual(self.req('/api/messages',{'room':'another-room','text':'intrude'},bc)[0],403)
  self.assertEqual(self.req('/api/statuses',{'text':'Private moment','color':'#244f38'},ac)[0],200)
  self.assertEqual(len(self.req('/api/statuses',cookie=bc)[1]['statuses']),0)
  self.req('/api/contacts',{'phone':'+94771111111'},bc)
  statuses=self.req('/api/statuses',cookie=bc)[1]['statuses'];self.assertEqual(len(statuses),1)
  self.req('/api/status/delete',{'id':statuses[0]['id']},bc)
  self.assertEqual(len(self.req('/api/statuses',cookie=ac)[1]['statuses']),1)
  with server.db() as c:c.execute('UPDATE statuses SET created=?',(time.time()-90000,))
  self.assertEqual(len(self.req('/api/statuses',cookie=ac)[1]['statuses']),0)
  self.assertEqual(self.req('/api/messages',{'room':room,'text':'','file':{'url':'data:text/html;base64,PHNjcmlwdD4=','name':'evil.html'}},ac)[0],400)
  self.assertEqual(self.req('/api/block',{'user':aid},bc)[0],200)
  self.assertEqual(self.req('/api/messages',{'room':room,'text':'blocked'},ac)[0],403)
  self.assertEqual(self.req('/api/logout',{},ac)[0],200)
  self.assertEqual(self.req('/api/me',cookie=ac)[0],401)
  with server.db() as c:
   self.assertNotIn('Alice-password',c.execute('SELECT password FROM users WHERE id=?',(aid,)).fetchone()[0])
 def test_static_pwa_assets(self):
  for p in ['/','/enhancements.js','/manifest.webmanifest','/sw.js','/icon-192.png']:
   status,body,headers=self.req(p);self.assertEqual(status,200,p);self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
  self.assertEqual(self.req('/server.py')[0],404)
if __name__=='__main__':unittest.main()
