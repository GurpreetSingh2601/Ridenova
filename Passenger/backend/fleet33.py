"""Build 33 driver access and account operations for the local development backend."""
import hashlib
import hmac
import secrets
import sqlite3

from fleet30 import Fleet as PreviousFleet, FleetError, reject, KINDS


class Fleet(PreviousFleet):
    def __init__(self, service):
        super().__init__(service)
        if service.postgres:
            return
        with service.connect() as db:
            columns = {row[1] for row in db.execute('PRAGMA table_info(fleet_logins)')}
            if 'phone' not in columns:
                db.execute('ALTER TABLE fleet_logins ADD COLUMN phone TEXT')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS fleet_login_phone '
                       'ON fleet_logins(phone) WHERE phone IS NOT NULL')

    @staticmethod
    def phone(value, required=False):
        if value in (None, '') and not required:
            return None
        if not isinstance(value, str):
            reject(400, 'INVALID_PHONE', 'Enter a valid Canadian mobile number')
        digits = ''.join(character for character in value if character.isdigit())
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]
        if len(digits) != 10 or digits[0] not in '23456789' or digits[3] not in '23456789':
            reject(400, 'INVALID_PHONE', 'Enter a valid Canadian 10-digit mobile number')
        return '+1' + digits

    @staticmethod
    def masked_phone(value):
        return None if not value else '(***) ***-' + value[-4:]

    def _free_phone(self, db, phone, driver=None):
        if not phone:
            return
        row = db.execute('SELECT driver_id FROM fleet_logins WHERE phone=?', (phone,)).fetchone()
        if row and row[0] != driver:
            reject(409, 'PHONE_TAKEN', 'This phone number is already linked to another driver account')

    def register_account(self, body):
        username = self.username(body.get('username'))
        phone = self.phone(body.get('phone'))
        password = self.password(body.get('password'))
        fields = []
        for key, limit in (('name', 80), ('vehicle', 100), ('plate', 20)):
            value = body.get(key)
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
                reject(400, 'INVALID_PROFILE', 'Invalid ' + key)
            fields.append(value.strip())
        category = body.get('category')
        if category not in self.service.config['tiers']:
            reject(400, 'INVALID_CATEGORY', 'Unknown category')
        salt = secrets.token_hex(16)
        digest = self.password_hash(password, salt)
        driver, token = 'drv_' + secrets.token_hex(12), secrets.token_urlsafe(40)
        try:
            with self.auth_lock, self.service.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                self._free_username(db, username)
                self._free_phone(db, phone)
                db.execute('INSERT INTO fleet_drivers(id,name,vehicle,plate,category,created_ms) VALUES (?,?,?,?,?,?)',
                           (driver, *fields, category, self.service.clock()))
                db.execute('INSERT INTO fleet_credentials VALUES (?,?)',
                           (hashlib.sha256(token.encode()).hexdigest(), driver))
                db.execute('INSERT INTO fleet_logins(driver_id,username,salt,password_hash,must_reset,phone) '
                           'VALUES (?,?,?,?,0,?)', (driver, username, salt, digest, phone))
                for kind in KINDS:
                    db.execute('INSERT INTO fleet_documents(driver_id,kind) VALUES (?,?)', (driver, kind))
                self._audit(db, driver, 'driver', 'ACCOUNT_CREATED')
        except sqlite3.IntegrityError:
            reject(409, 'ACCOUNT_TAKEN', 'That username or phone number is already in use')
        return {'driverId': driver, 'username': username, 'maskedPhone': self.masked_phone(phone),
                'developmentToken': token, 'status': 'PENDING', 'developmentOnly': True}

    def _identity(self, body):
        value = body.get('identifier', body.get('username'))
        if not isinstance(value, str) or not value.strip():
            reject(400, 'INVALID_LOGIN', 'Enter your username or Canadian phone number')
        raw = value.strip()
        digits = ''.join(character for character in raw if character.isdigit())
        if any(character.isalpha() or character in '._' for character in raw) or len(digits) not in (10, 11):
            return 'username', self.username(raw), 'u:' + self.username(raw)
        phone = self.phone(raw, required=True)
        return 'phone', phone, 'p:' + phone

    def login(self, body):
        field, identity, attempt_key = self._identity(body)
        password = self.password(body.get('password'))
        failed = False
        with self.auth_lock, self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now = self.service.clock()
            db.execute('DELETE FROM fleet_login_attempts WHERE until_ms<=?', (now,))
            attempt = db.execute('SELECT failures,until_ms FROM fleet_login_attempts WHERE username=?',
                                 (attempt_key,)).fetchone()
            if attempt and attempt[0] >= 5:
                reject(429, 'LOGIN_LOCKED', 'Too many attempts. Wait one minute before trying again')
            row = db.execute(
                f'SELECT driver_id,username,salt,password_hash,must_reset,phone FROM fleet_logins WHERE {field}=?',
                (identity,)).fetchone()
            salt = row[2] if row else '00' * 16
            digest = self.password_hash(password, salt)
            valid = row and not row[4] and hmac.compare_digest(digest, row[3])
            if not valid:
                failures = (attempt[0] if attempt else 0) + 1
                db.execute('INSERT OR REPLACE INTO fleet_login_attempts VALUES (?,?,?)',
                           (attempt_key, failures, now + 60000))
                failed = True
            else:
                driver, username, phone = row[0], row[1], row[5]
                token = secrets.token_urlsafe(40)
                db.execute('UPDATE fleet_credentials SET token_hash=? WHERE driver_id=?',
                           (hashlib.sha256(token.encode()).hexdigest(), driver))
                if not self.active(db, driver):
                    db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?', (driver,))
                    db.execute('DELETE FROM fleet_offers WHERE driver_id=?', (driver,))
                db.execute('DELETE FROM fleet_login_attempts WHERE username=?', (attempt_key,))
                self._audit(db, driver, 'driver', 'SIGNED_IN')
        if failed:
            reject(401, 'INVALID_LOGIN', 'Incorrect username/phone or password, or access needs recovery')
        return {'driverId': driver, 'username': username, 'maskedPhone': self.masked_phone(phone),
                'developmentToken': token, 'developmentOnly': True}

    def login_details(self, driver):
        with self.service.connect() as db:
            row = db.execute('SELECT username,must_reset,phone FROM fleet_logins WHERE driver_id=?',
                             (driver,)).fetchone()
        return {'username': row[0] if row else None, 'loginConfigured': bool(row),
                'needsRecovery': bool(row and row[1]),
                'maskedPhone': self.masked_phone(row[2]) if row else None,
                'phoneConfigured': bool(row and row[2])}

    def set_login(self, driver, body):
        username = self.username(body.get('username'))
        phone = self.phone(body.get('phone'))
        salt = secrets.token_hex(16)
        digest = self.password_hash(self.password(body.get('password')), salt)
        with self.auth_lock, self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM fleet_logins WHERE driver_id=?', (driver,)).fetchone():
                reject(409, 'LOGIN_EXISTS', 'Sign-in is already configured. Use account recovery to reset it')
            self._free_username(db, username)
            self._free_phone(db, phone)
            db.execute('INSERT INTO fleet_logins(driver_id,username,salt,password_hash,must_reset,phone) '
                       'VALUES (?,?,?,?,0,?)', (driver, username, salt, digest, phone))
            self._audit(db, driver, 'driver', 'LOGIN_CONFIGURED')
        return self.login_details(driver)

    def change_password(self, driver, body):
        current = self.password(body.get('currentPassword'))
        replacement = self.password(body.get('newPassword'))
        if hmac.compare_digest(current, replacement):
            reject(400, 'PASSWORD_UNCHANGED', 'Choose a different new password')
        with self.auth_lock, self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT salt,password_hash FROM fleet_logins WHERE driver_id=?',
                             (driver,)).fetchone()
            if not row:
                reject(409, 'LOGIN_REQUIRED', 'Create sign-in details first')
            if not hmac.compare_digest(self.password_hash(current, row[0]), row[1]):
                reject(401, 'CURRENT_PASSWORD_INCORRECT', 'Current password is incorrect')
            salt = secrets.token_hex(16)
            db.execute('UPDATE fleet_logins SET salt=?,password_hash=?,must_reset=0 WHERE driver_id=?',
                       (salt, self.password_hash(replacement, salt), driver))
            self._audit(db, driver, 'driver', 'PASSWORD_CHANGED')
        return {'changed': True}

    def account_overview(self, driver):
        status = self.status(driver)
        documents = self.documents(driver)['documents']
        trips = self.history(driver)['trips']
        status.update(self.login_details(driver))
        status['documents'] = {
            'approved': sum(item['status'] == 'APPROVED' and not item['expired'] for item in documents),
            'required': len(KINDS),
            'pending': sum(item['status'] == 'PENDING' for item in documents),
            'rejected': sum(item['status'] == 'REJECTED' or item['expired'] for item in documents),
        }
        status['lifetime'] = {
            'completedTrips': len(trips),
            'estimatedEarningsCad': round(sum(item['driverEarningsCad'] for item in trips), 2),
            'distanceKm': round(sum(item['distanceKm'] for item in trips), 1),
        }
        return status

    def recover(self, body):
        # The recovery credential still proves account ownership. Resolve a phone identifier
        # while preserving the account's existing phone during the password reset.
        recovery = body.get('recoveryToken')
        if not isinstance(recovery, str):
            reject(401, 'FLEET_AUTH_REQUIRED', 'Enter the recovery credential from your admin')
        field, identity, _ = self._identity(body)
        if field == 'phone':
            with self.service.connect() as db:
                row = db.execute('SELECT username FROM fleet_logins WHERE phone=?', (identity,)).fetchone()
            if not row:
                reject(401, 'FLEET_AUTH_REQUIRED', 'Account recovery details are incorrect')
            username = row[0]
        else:
            username = identity
        password = self.password(body.get('password'))
        salt = secrets.token_hex(16)
        digest = self.password_hash(password, salt)
        with self.auth_lock:
            driver = self.authenticate('Bearer ' + recovery)
            with self.service.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if self.active(db, driver):
                    reject(409, 'ACTIVE_RIDE', 'Finish the active ride before resetting sign-in')
                self._free_username(db, username, driver)
                old = db.execute('SELECT username,phone FROM fleet_logins WHERE driver_id=?',
                                 (driver,)).fetchone()
                if old and old[0] != username:
                    reject(400, 'USERNAME_MISMATCH', 'Use the existing username shown by your admin')
                phone = old[1] if old else self.phone(body.get('phone'))
                self._free_phone(db, phone, driver)
                db.execute('INSERT OR REPLACE INTO fleet_logins '
                           '(driver_id,username,salt,password_hash,must_reset,phone) VALUES (?,?,?,?,0,?)',
                           (driver, username, salt, digest, phone))
                token = secrets.token_urlsafe(40)
                db.execute('UPDATE fleet_credentials SET token_hash=? WHERE driver_id=?',
                           (hashlib.sha256(token.encode()).hexdigest(), driver))
                db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?', (driver,))
                db.execute('DELETE FROM fleet_offers WHERE driver_id=?', (driver,))
                db.execute('DELETE FROM fleet_login_attempts WHERE username IN (?,?)',
                           ('u:' + username, username))
                self._audit(db, driver, 'driver', 'LOGIN_RECOVERED')
        return {'driverId': driver, 'username': username, 'maskedPhone': self.masked_phone(phone),
                'developmentToken': token, 'developmentOnly': True}
