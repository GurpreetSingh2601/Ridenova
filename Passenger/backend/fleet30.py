"""Build 30 driver accounts for the loopback development backend."""
import hashlib
import hmac
import re
import secrets
import threading
from fleet29 import Fleet as PreviousFleet, FleetError, reject, KINDS

ITERATIONS = 600_000

class Fleet(PreviousFleet):
    def __init__(self, service):
        super().__init__(service)
        # Serializes authentication + mutation against logout/login/reset in this server.
        self.auth_lock = threading.RLock()
        if service.postgres:
            return
        with service.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS fleet_logins (
                    driver_id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    salt TEXT NOT NULL, password_hash TEXT NOT NULL,
                    must_reset INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS fleet_login_attempts (
                    username TEXT PRIMARY KEY, failures INTEGER NOT NULL, until_ms INTEGER NOT NULL);
            ''')

    @staticmethod
    def username(value):
        if not isinstance(value, str): reject(400, 'INVALID_USERNAME', 'Choose a username with 3–40 letters, numbers, dots, underscores or hyphens')
        value = value.strip().lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,39}', value):
            reject(400, 'INVALID_USERNAME', 'Choose a username with 3–40 letters, numbers, dots, underscores or hyphens')
        return value

    @staticmethod
    def password(value):
        if not isinstance(value, str) or not 10 <= len(value) <= 128 or not value.strip():
            reject(400, 'INVALID_PASSWORD', 'Use a password of 10–128 characters')
        return value

    @staticmethod
    def password_hash(password, salt):
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), ITERATIONS).hex()

    def _free_username(self, db, username, driver=None):
        row = db.execute('SELECT driver_id FROM fleet_logins WHERE username=?', (username,)).fetchone()
        if row and row[0] != driver: reject(409, 'USERNAME_TAKEN', 'This username is already in use')

    def register_account(self, body):
        username = self.username(body.get('username'))
        password = self.password(body.get('password'))
        fields = []
        for key, limit in (('name',80),('vehicle',100),('plate',20)):
            value = body.get(key)
            if not isinstance(value,str) or not 1 <= len(value.strip()) <= limit:
                reject(400, 'INVALID_PROFILE', 'Invalid ' + key)
            fields.append(value.strip())
        category = body.get('category')
        if category not in self.service.config['tiers']: reject(400,'INVALID_CATEGORY','Unknown category')
        salt = secrets.token_hex(16)
        digest = self.password_hash(password, salt)
        driver, token = 'drv_' + secrets.token_hex(12), secrets.token_urlsafe(40)
        with self.auth_lock, self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._free_username(db, username)
            db.execute('INSERT INTO fleet_drivers(id,name,vehicle,plate,category,created_ms) VALUES (?,?,?,?,?,?)',
                       (driver,*fields,category,self.service.clock()))
            db.execute('INSERT INTO fleet_credentials VALUES (?,?)',(hashlib.sha256(token.encode()).hexdigest(),driver))
            db.execute('INSERT INTO fleet_logins VALUES (?,?,?,?,0)',(driver,username,salt,digest))
            for kind in KINDS: db.execute('INSERT INTO fleet_documents(driver_id,kind) VALUES (?,?)',(driver,kind))
            self._audit(db,driver,'driver','ACCOUNT_CREATED')
        return {'driverId':driver,'username':username,'developmentToken':token,'status':'PENDING','developmentOnly':True}

    def login(self, body):
        username = self.username(body.get('username'))
        password = self.password(body.get('password'))
        failed = False
        with self.auth_lock, self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now = self.service.clock()
            db.execute('DELETE FROM fleet_login_attempts WHERE until_ms<=?',(now,))
            attempt = db.execute('SELECT failures,until_ms FROM fleet_login_attempts WHERE username=?',(username,)).fetchone()
            if attempt and attempt[0] >= 5:
                reject(429,'LOGIN_LOCKED','Too many attempts. Wait one minute before trying again')
            row = db.execute('SELECT driver_id,salt,password_hash,must_reset FROM fleet_logins WHERE username=?',(username,)).fetchone()
            # Similar password cost for unknown usernames; passwords never appear in audit logs.
            salt = row[1] if row else '00' * 16
            digest = self.password_hash(password, salt)
            valid = row and not row[3] and hmac.compare_digest(digest,row[2])
            if not valid:
                failures = (attempt[0] if attempt else 0) + 1
                db.execute('INSERT OR REPLACE INTO fleet_login_attempts VALUES (?,?,?)',(username,failures,now+60000))
                failed = True
            else:
                driver = row[0]
                token = secrets.token_urlsafe(40)
                db.execute('UPDATE fleet_credentials SET token_hash=? WHERE driver_id=?',(hashlib.sha256(token.encode()).hexdigest(),driver))
                # A new sign-in can recover an assigned ride. Idle accounts always start offline.
                if not self.active(db,driver):
                    db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?',(driver,))
                    db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver,))
                db.execute('DELETE FROM fleet_login_attempts WHERE username=?',(username,))
                self._audit(db,driver,'driver','SIGNED_IN')
        if failed: reject(401,'INVALID_LOGIN','Incorrect username/password, or access needs recovery')
        return {'driverId':driver,'username':username,'developmentToken':token,'developmentOnly':True}

    def login_details(self, driver):
        with self.service.connect() as db:
            row = db.execute('SELECT username,must_reset FROM fleet_logins WHERE driver_id=?',(driver,)).fetchone()
        return {'username':row[0] if row else None,'loginConfigured':bool(row),'needsRecovery':bool(row and row[1])}

    def set_login(self, driver, body):
        username = self.username(body.get('username'))
        salt = secrets.token_hex(16)
        digest = self.password_hash(self.password(body.get('password')),salt)
        with self.auth_lock, self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM fleet_logins WHERE driver_id=?',(driver,)).fetchone():
                reject(409,'LOGIN_EXISTS','Sign-in is already configured. Use account recovery to reset it')
            self._free_username(db,username)
            db.execute('INSERT INTO fleet_logins VALUES (?,?,?,?,0)',(driver,username,salt,digest))
            self._audit(db,driver,'driver','LOGIN_CONFIGURED')
        return self.login_details(driver)

    def logout(self, driver):
        with self.auth_lock, self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.active(db,driver): reject(409,'ACTIVE_RIDE','Finish or cancel your active ride before signing out')
            if not db.execute('SELECT 1 FROM fleet_logins WHERE driver_id=?',(driver,)).fetchone():
                reject(409,'LOGIN_REQUIRED','Create your username and password before signing out')
            db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?',(driver,))
            db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver,))
            # Retain the row for later sign-in; nobody knows this replacement token.
            db.execute('UPDATE fleet_credentials SET token_hash=? WHERE driver_id=?',(hashlib.sha256(secrets.token_bytes(40)).hexdigest(),driver))
            self._audit(db,driver,'driver','SIGNED_OUT')
        return {'signedOut':True}

    def rotate_token(self, driver):
        with self.auth_lock:
            result = super().rotate_token(driver)
            with self.service.connect() as db:
                db.execute('UPDATE fleet_logins SET must_reset=1 WHERE driver_id=?',(driver,))
            return result

    def recover(self, body):
        recovery = body.get('recoveryToken')
        if not isinstance(recovery,str): reject(401,'FLEET_AUTH_REQUIRED','Enter the recovery credential from your admin')
        username = self.username(body.get('username'))
        salt = secrets.token_hex(16)
        digest = self.password_hash(self.password(body.get('password')),salt)
        with self.auth_lock:
            driver = self.authenticate('Bearer ' + recovery)
            with self.service.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if self.active(db,driver): reject(409,'ACTIVE_RIDE','Finish the active ride before resetting sign-in')
                self._free_username(db,username,driver)
                old=db.execute('SELECT username FROM fleet_logins WHERE driver_id=?',(driver,)).fetchone()
                if old and old[0]!=username: reject(400,'USERNAME_MISMATCH','Use the existing username shown by your admin')
                db.execute('INSERT OR REPLACE INTO fleet_logins VALUES (?,?,?,?,0)',(driver,username,salt,digest))
                token=secrets.token_urlsafe(40)
                db.execute('UPDATE fleet_credentials SET token_hash=? WHERE driver_id=?',(hashlib.sha256(token.encode()).hexdigest(),driver))
                db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?',(driver,))
                db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver,))
                db.execute('DELETE FROM fleet_login_attempts WHERE username=?',(username,))
                self._audit(db,driver,'driver','LOGIN_RECOVERED')
        return {'driverId':driver,'username':username,'developmentToken':token,'developmentOnly':True}

    def status(self, driver):
        result=super().status(driver)
        result.update(self.login_details(driver))
        return result
