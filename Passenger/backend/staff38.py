"""Development-only individually authenticated admin staff accounts.
Do not expose this development server to the public internet.
"""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from database import connect, is_postgres

ROLES = ('OWNER', 'OPERATIONS', 'SUPPORT', 'FINANCE', 'COMPLIANCE')
PERMS = {
    'OWNER': {'overview','fleet.read','fleet.write','documents.read','documents.write','finance.read','finance.write','support.read','support.write','ride.read','ride.write','staff.read','staff.write','audit.read'},
    'OPERATIONS': {'overview','fleet.read','fleet.write','documents.read','documents.write','ride.read','ride.write','support.read','support.write'},
    'SUPPORT': {'overview','ride.read','support.read','support.write'},
    'FINANCE': {'overview','finance.read','ride.read'},
    'COMPLIANCE': {'overview','fleet.read','documents.read','documents.write','audit.read'},
}
class StaffError(Exception):
    def __init__(self,status,code,message):
        self.status,self.code,self.message=status,code,message

def reject(status, code, message): raise StaffError(status,code,message)

class Staff:
    def __init__(self, database):
        self.database=str(database)
        if is_postgres(self.database):
            return  # Schema and owner bootstrap are explicit deployment steps.
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS admin_staff(
                id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, role TEXT NOT NULL,
                salt TEXT NOT NULL, secret_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                created_ms INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS admin_sessions(
                token_hash TEXT PRIMARY KEY, staff_id TEXT NOT NULL, expires_ms INTEGER NOT NULL,
                FOREIGN KEY(staff_id) REFERENCES admin_staff(id));
            CREATE TABLE IF NOT EXISTS admin_audit(
                id INTEGER PRIMARY KEY AUTOINCREMENT, at_ms INTEGER NOT NULL, actor TEXT NOT NULL,
                action TEXT NOT NULL, subject TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS admin_audit_time ON admin_audit(at_ms DESC);
            ''')
        # Explicit one-time local bootstrap only. Never ship credentials or auto-create default passwords.
        name=os.environ.get('RIDENOVA_OWNER_USERNAME','').strip().lower()
        password=os.environ.get('RIDENOVA_OWNER_PASSWORD','')
        if name and password:
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                count=db.execute('SELECT COUNT(*) FROM admin_staff').fetchone()[0]
                if count==0:
                    if len(password)<14: raise ValueError('RIDENOVA_OWNER_PASSWORD must be >=14 characters')
                    self._create(db,name,password,'OWNER','bootstrap')

    @contextmanager
    def connect(self):
        db=connect(self.database)
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
    @staticmethod
    def _hash(password,salt):
        return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),350000).hex()
    def _audit(self,db,actor,action,subject):
        db.execute('INSERT INTO admin_audit(at_ms,actor,action,subject) VALUES (?,?,?,?)',
                   (int(time.time()*1000),actor,action,subject))
    def _create(self,db,username,password,role,actor):
        if not re.fullmatch(r'[a-z0-9._-]{3,48}',username) or role not in ROLES or not isinstance(password,str) or len(password)<14 or len(password)>256:
            reject(400,'INVALID_STAFF','Invalid username, role or password (14-256 characters required)')
        sid='staff_'+secrets.token_hex(12);salt=secrets.token_hex(16)
        try:
            db.execute('INSERT INTO admin_staff VALUES (?,?,?,?,?,1,?)',
                (sid,username,role,salt,self._hash(password,salt),int(time.time()*1000)))
        except sqlite3.IntegrityError: reject(409,'DUPLICATE_STAFF','Username already exists')
        self._audit(db,actor,'STAFF_CREATED',sid)
        return {'id':sid,'username':username,'role':role,'active':True}
    def login(self,body):
        name=body.get('username','');password=body.get('password','')
        if not isinstance(name,str) or not isinstance(password,str) or len(password)>256:
            reject(401,'INVALID_LOGIN','Invalid credentials')
        with self.connect() as db:
            row=db.execute('SELECT id,role,salt,secret_hash,active FROM admin_staff WHERE username=?',(name.strip().lower(),)).fetchone()
            candidate=self._hash(password,row[2] if row else '00'*16)
            if not row or not row[4] or not hmac.compare_digest(row[3],candidate):
                reject(401,'INVALID_LOGIN','Invalid credentials')
            token=secrets.token_urlsafe(40)
            db.execute('INSERT INTO admin_sessions VALUES (?,?,?)',
                (hashlib.sha256(token.encode()).hexdigest(),row[0],int(time.time()*1000)+8*3600000))
            self._audit(db,row[0],'STAFF_LOGIN',row[0])
            return {'accessToken':token,'expiresInSeconds':28800,'staff':{'id':row[0],'username':name.strip().lower(),'role':row[1]}}
    def authorize(self,authorization,permission):
        token=authorization[7:] if isinstance(authorization,str) and authorization.startswith('Bearer ') else ''
        if not token: reject(401,'STAFF_AUTH_REQUIRED','Staff sign-in required')
        digest=hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as db:
            row=db.execute('''SELECT s.id,s.username,s.role,s.active,a.expires_ms FROM admin_sessions a
                JOIN admin_staff s ON s.id=a.staff_id WHERE a.token_hash=?''',(digest,)).fetchone()
        if not row or not row[3] or row[4]<=int(time.time()*1000):
            reject(401,'STAFF_AUTH_REQUIRED','Session expired or account disabled')
        if permission not in PERMS[row[2]]: reject(403,'STAFF_FORBIDDEN','Insufficient permission')
        return {'id':row[0],'username':row[1],'role':row[2]}
    def logout(self,authorization):
        actor=self.authorize(authorization,'overview')
        token=authorization[7:]
        digest=hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as db:
            db.execute('DELETE FROM admin_sessions WHERE token_hash=?',(digest,))
            self._audit(db,actor['id'],'STAFF_LOGOUT',actor['id'])
        return {'signedOut':True}

    def create(self,actor,body):
        with self.connect() as db:
            return self._create(db,str(body.get('username','')).strip().lower(),body.get('password',''),body.get('role',''),actor['id'])
    def list(self):
        with self.connect() as db:
            rows=db.execute('SELECT id,username,role,active,created_ms FROM admin_staff ORDER BY created_ms').fetchall()
        return {'staff':[dict(zip(('id','username','role','active','createdAtEpochMs'),(a,b,c,bool(d),e))) for a,b,c,d,e in rows]}
    def set_active(self,actor,staff_id,active):
        if type(active) is not bool: reject(400,'INVALID_STATUS','active must be boolean')
        if actor['id']==staff_id and not active: reject(409,'SELF_DISABLE','Cannot disable your own account')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT role FROM admin_staff WHERE id=?',(staff_id,)).fetchone()
            if not row: reject(404,'NOT_FOUND','Staff account not found')
            if row[0]=='OWNER' and not active and db.execute("SELECT COUNT(*) FROM admin_staff WHERE role='OWNER' AND active=1").fetchone()[0]<=1:
                reject(409,'LAST_OWNER','Cannot disable last owner')
            db.execute('UPDATE admin_staff SET active=? WHERE id=?',(int(active),staff_id))
            if not active: db.execute('DELETE FROM admin_sessions WHERE staff_id=?',(staff_id,))
            self._audit(db,actor['id'],'STAFF_ACTIVATED' if active else 'STAFF_DISABLED',staff_id)
        return {'id':staff_id,'active':active}
    def audit(self):
        with self.connect() as db:
            rows=db.execute('SELECT at_ms,actor,action,subject FROM admin_audit ORDER BY id DESC LIMIT 100').fetchall()
        return {'events':[dict(zip(('atEpochMs','actor','action','subject'),row)) for row in rows]}
    def record(self,actor,action,subject):
        with self.connect() as db:self._audit(db,actor['id'],action,subject)
