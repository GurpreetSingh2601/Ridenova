"""RideNova Build 41 shared API. Python 3.11+.

This CLI is loopback development only; staging uses wsgi.py with Gunicorn.
The displayed development OTP does not prove ownership of a real phone number.
"""
import argparse
import hashlib
import json
import math
import os
import secrets
import sqlite3
import time
import threading
from datetime import datetime, timezone
import urllib.request
import re
from decimal import Decimal, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from database import connect, is_postgres


class APIError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def fail(status, code, message):
    raise APIError(status, code, message)


def cents(value):
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def decode_polyline(encoded):
    """Decode Google's polyline into JSON-safe latitude/longitude points."""
    points, index, latitude, longitude = [], 0, 0, 0
    while index < len(encoded):
        values = []
        for _ in range(2):
            result = shift = 0
            while index < len(encoded):
                value = ord(encoded[index]) - 63; index += 1
                result |= (value & 0x1f) << shift; shift += 5
                if value < 0x20: break
            values.append(~(result >> 1) if result & 1 else result >> 1)
        latitude += values[0]; longitude += values[1]
        points.append({'latitude': latitude / 100000.0, 'longitude': longitude / 100000.0})
    return points


LIVE_STATES = ('SEARCHING', 'DRIVER_ASSIGNED', 'DRIVER_ARRIVED', 'TRIP_STARTED')
TERMINAL_STATES = ('COMPLETED', 'CANCELLED_BY_RIDER', 'SCHEDULE_EXPIRED')
ACCESS_TTL_MS = 15 * 60 * 1000
REFRESH_TTL_MS = 30 * 24 * 60 * 60 * 1000
OTP_TTL_MS = 5 * 60 * 1000
OTP_RESEND_MS = 60 * 1000
DEV_OTP = '246810'


class ClosingConnection(sqlite3.Connection):
    """Commit/rollback AND close a database connection when leaving a with block.

    sqlite3.Connection's default context manager does not close the connection;
    on Windows that can prevent deletion of temporary test databases.
    """
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class Service:
    def __init__(self, database, config=None, clock=None, route_provider=None):
        self.database = str(database)
        self.config = config or json.loads(Path(__file__).with_name('market.json').read_text())
        self.clock = clock or (lambda: int(time.time() * 1000))
        self.route_provider = route_provider or self.route
        self.postgres = is_postgres(self.database)
        if self.postgres:
            self._components()
            return
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS quotes (
                    token TEXT PRIMARY KEY, owner TEXT NOT NULL, expires INTEGER NOT NULL,
                    payload TEXT NOT NULL, ride_id TEXT);
                CREATE TABLE IF NOT EXISTS rides (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, ride_id TEXT NOT NULL,
                    at_ms INTEGER NOT NULL, actor TEXT NOT NULL, type TEXT NOT NULL,
                    payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS passengers (
                    id TEXT PRIMARY KEY, phone TEXT NOT NULL UNIQUE, first_name TEXT NOT NULL DEFAULT '',
                    last_name TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '', created_ms INTEGER NOT NULL,
                    updated_ms INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS otp_challenges (
                    id TEXT PRIMARY KEY, phone TEXT NOT NULL, code_hash TEXT NOT NULL, created_ms INTEGER NOT NULL,
                    expires_ms INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, consumed_ms INTEGER);
                CREATE INDEX IF NOT EXISTS otp_phone_created ON otp_challenges(phone, created_ms);
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id TEXT PRIMARY KEY, passenger_id TEXT NOT NULL, access_hash TEXT NOT NULL UNIQUE,
                    access_expires_ms INTEGER NOT NULL, refresh_hash TEXT NOT NULL UNIQUE,
                    refresh_expires_ms INTEGER NOT NULL, revoked_ms INTEGER,
                    FOREIGN KEY(passenger_id) REFERENCES passengers(id));
                CREATE TABLE IF NOT EXISTS saved_places (
                    passenger_id TEXT NOT NULL, slot TEXT NOT NULL, payload TEXT NOT NULL,
                    updated_ms INTEGER NOT NULL, PRIMARY KEY(passenger_id, slot),
                    FOREIGN KEY(passenger_id) REFERENCES passengers(id));
                CREATE TABLE IF NOT EXISTS recent_destinations (
                    passenger_id TEXT NOT NULL, identity TEXT NOT NULL, payload TEXT NOT NULL,
                    used_ms INTEGER NOT NULL, PRIMARY KEY(passenger_id, identity),
                    FOREIGN KEY(passenger_id) REFERENCES passengers(id));
                CREATE INDEX IF NOT EXISTS recent_destinations_used
                    ON recent_destinations(passenger_id, used_ms DESC);
                CREATE TABLE IF NOT EXISTS payment_methods (
                    id TEXT PRIMARY KEY, passenger_id TEXT NOT NULL, type TEXT NOT NULL,
                    brand TEXT NOT NULL, last4 TEXT NOT NULL, expiry_month INTEGER NOT NULL,
                    expiry_year INTEGER NOT NULL, is_default INTEGER NOT NULL DEFAULT 0,
                    created_ms INTEGER NOT NULL,
                    FOREIGN KEY(passenger_id) REFERENCES passengers(id));
                CREATE INDEX IF NOT EXISTS payment_methods_passenger
                    ON payment_methods(passenger_id, is_default DESC, created_ms);
                CREATE TABLE IF NOT EXISTS driver_state (
                    id INTEGER PRIMARY KEY CHECK(id=1), online INTEGER NOT NULL DEFAULT 0,
                    name TEXT NOT NULL DEFAULT 'Development driver',
                    vehicle TEXT NOT NULL DEFAULT 'Test vehicle', plate TEXT NOT NULL DEFAULT 'DEMO');
                CREATE TABLE IF NOT EXISTS driver_declines (
                    ride_id TEXT PRIMARY KEY, until_ms INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS driver_presence (
                    id INTEGER PRIMARY KEY CHECK(id=1), latitude REAL NOT NULL, longitude REAL NOT NULL,
                    recorded_ms INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS driver_offer_state (
                    id INTEGER PRIMARY KEY CHECK(id=1), ride_id TEXT NOT NULL, expires_ms INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS development_earnings (
                    ride_id TEXT PRIMARY KEY, completed_ms INTEGER NOT NULL,
                    fare_subtotal_cents INTEGER NOT NULL, gst_cents INTEGER NOT NULL,
                    passenger_total_cents INTEGER NOT NULL, platform_commission_cents INTEGER NOT NULL,
                    driver_gross_before_costs_cents INTEGER NOT NULL,
                    CHECK (fare_subtotal_cents >= 0 AND gst_cents >= 0 AND passenger_total_cents >= 0));
            ''')

        self._components()

    def _components(self):
        from fleet35 import Fleet
        self.fleet = Fleet(self)
        from experience34 import Experience
        self.experience = Experience(self)

    @staticmethod
    def token_hash(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def normalize_phone(self, value):
        if not isinstance(value, str):
            fail(400, 'INVALID_PHONE', 'Enter a Canadian 10-digit mobile number')
        digits = ''.join(c for c in value if c.isdigit())
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]
        if len(digits) != 10 or digits[0] not in '23456789' or digits[3] not in '23456789':
            fail(400, 'INVALID_PHONE', 'Enter a valid Canadian +1 phone number')
        return '+1' + digits

    def request_otp(self, body):
        phone = self.normalize_phone(body.get('phone'))
        settings = getattr(self, 'settings', None)
        staging = settings is not None and settings.environment == 'staging'
        code = DEV_OTP
        if staging:
            from operations import allow_request
            if phone not in settings.tester_codes:
                fail(403, 'STAGING_INVITE_REQUIRED', 'This staging build is for invited testers')
            if not allow_request(self.database, settings.rate_secret, 'otp-phone:' + phone, 5, 3600):
                fail(429, 'OTP_RATE_LIMITED', 'Staging sign-in limit reached; try again later')
            code = settings.tester_codes[phone]
        now = self.clock()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            recent = db.execute('SELECT created_ms FROM otp_challenges WHERE phone=? ORDER BY created_ms DESC LIMIT 1', (phone,)).fetchone()
            if recent and now - recent[0] < OTP_RESEND_MS:
                fail(429, 'OTP_RATE_LIMITED', 'Wait one minute before requesting another code')
            challenge = 'otp_' + secrets.token_urlsafe(18)
            code_hash = self.token_hash(challenge + ':' + code)
            db.execute('INSERT INTO otp_challenges(id,phone,code_hash,created_ms,expires_ms) VALUES (?,?,?,?,?)',
                       (challenge, phone, code_hash, now, now + OTP_TTL_MS))
        if staging:
            return {'challengeId': challenge, 'expiresAtEpochMs': now + OTP_TTL_MS,
                    'resendAfterSeconds': 60, 'delivery': 'staging-invitation'}
        return {'challengeId': challenge, 'expiresAtEpochMs': now + OTP_TTL_MS,
                'resendAfterSeconds': 60, 'developmentCode': DEV_OTP, 'delivery': 'development'}

    def issue_tokens(self, db, passenger_id):
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        now, session_id = self.clock(), 'auth_' + secrets.token_hex(12)
        db.execute('INSERT INTO auth_sessions VALUES (?,?,?,?,?,?,NULL)',
                   (session_id, passenger_id, self.token_hash(access), now + ACCESS_TTL_MS,
                    self.token_hash(refresh), now + REFRESH_TTL_MS))
        return {'accessToken': access, 'accessExpiresAtEpochMs': now + ACCESS_TTL_MS,
                'refreshToken': refresh, 'refreshExpiresAtEpochMs': now + REFRESH_TTL_MS}

    def account_json(self, row):
        return {'id': row[0], 'phone': row[1], 'firstName': row[2], 'lastName': row[3], 'email': row[4],
                'profileComplete': bool(row[2].strip() and row[3].strip())}

    def verify_otp(self, body, legacy_owner):
        challenge, code = body.get('challengeId'), body.get('code')
        if not isinstance(challenge, str) or not isinstance(code, str):
            fail(400, 'INVALID_OTP', 'Enter the six-digit verification code')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT phone,code_hash,expires_ms,attempts,consumed_ms FROM otp_challenges WHERE id=?', (challenge,)).fetchone()
            if not row:
                fail(404, 'OTP_NOT_FOUND', 'Verification request not found; request a new code')
            settings = getattr(self, 'settings', None)
            if settings and settings.environment == 'staging' and row[0] not in settings.tester_codes:
                fail(403, 'STAGING_INVITE_REQUIRED', 'Staging invitation is no longer active')
            if row[4] is not None:
                fail(409, 'OTP_ALREADY_USED', 'This verification code has already been used')
            if self.clock() >= row[2]:
                fail(409, 'OTP_EXPIRED', 'Verification code expired; request a new code')
            if row[3] >= 5:
                fail(429, 'OTP_ATTEMPTS_EXCEEDED', 'Too many attempts; request a new code')
            if not secrets.compare_digest(row[1], self.token_hash(challenge + ':' + code)):
                db.execute('UPDATE otp_challenges SET attempts=attempts+1 WHERE id=?', (challenge,))
                db.commit()
                fail(401, 'OTP_INCORRECT', 'Incorrect verification code')
            db.execute('UPDATE otp_challenges SET consumed_ms=? WHERE id=?', (self.clock(), challenge))
            account = db.execute('SELECT id,phone,first_name,last_name,email FROM passengers WHERE phone=?', (row[0],)).fetchone()
            is_new = account is None
            if is_new:
                passenger_id = 'psg_' + secrets.token_hex(12)
                db.execute('INSERT INTO passengers(id,phone,created_ms,updated_ms) VALUES (?,?,?,?)',
                           (passenger_id, row[0], self.clock(), self.clock()))
                account = db.execute('SELECT id,phone,first_name,last_name,email FROM passengers WHERE id=?', (passenger_id,)).fetchone()
            self.ensure_default_payment(db, account[0])
            if legacy_owner:
                db.execute('UPDATE rides SET owner=? WHERE owner=?', (account[0], legacy_owner))
                db.execute('UPDATE quotes SET owner=? WHERE owner=?', (account[0], legacy_owner))
            tokens = self.issue_tokens(db, account[0])
            return {**tokens, 'passenger': self.account_json(account), 'isNewAccount': is_new,
                    'migratedLegacySession': bool(legacy_owner)}

    def authenticate(self, bearer):
        if not isinstance(bearer, str) or not bearer.startswith('Bearer '):
            fail(401, 'AUTH_REQUIRED', 'Sign in to continue')
        token = bearer[7:]
        if not token or len(token) > 256:
            fail(401, 'AUTH_REQUIRED', 'Sign in to continue')
        with self.connect() as db:
            row = db.execute('SELECT passenger_id,access_expires_ms,revoked_ms FROM auth_sessions WHERE access_hash=?',
                             (self.token_hash(token),)).fetchone()
        if not row or row[2] is not None or self.clock() >= row[1]:
            fail(401, 'ACCESS_EXPIRED', 'Session expired; refresh or sign in again')
        settings = getattr(self, 'settings', None)
        if settings and settings.environment == 'staging':
            with self.connect() as db:
                phone = db.execute('SELECT phone FROM passengers WHERE id=?', (row[0],)).fetchone()
            if not phone or phone[0] not in settings.tester_codes:
                fail(403, 'STAGING_INVITE_REQUIRED', 'Staging invitation is no longer active')
        return row[0]

    def refresh(self, body):
        token = body.get('refreshToken')
        if not isinstance(token, str) or not token:
            fail(401, 'REFRESH_REQUIRED', 'Refresh token required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT id,passenger_id,refresh_expires_ms,revoked_ms FROM auth_sessions WHERE refresh_hash=?',
                             (self.token_hash(token),)).fetchone()
            if not row or row[3] is not None or self.clock() >= row[2]:
                fail(401, 'REFRESH_EXPIRED', 'Please sign in again')
            db.execute('UPDATE auth_sessions SET revoked_ms=? WHERE id=?', (self.clock(), row[0]))
            return self.issue_tokens(db, row[1])

    def logout(self, bearer, refresh_token=None):
        with self.connect() as db:
            if isinstance(bearer, str) and bearer.startswith('Bearer '):
                db.execute('UPDATE auth_sessions SET revoked_ms=? WHERE access_hash=? AND revoked_ms IS NULL',
                           (self.clock(), self.token_hash(bearer[7:])))
            if isinstance(refresh_token, str) and refresh_token:
                db.execute('UPDATE auth_sessions SET revoked_ms=? WHERE refresh_hash=? AND revoked_ms IS NULL',
                           (self.clock(), self.token_hash(refresh_token)))
        return {'signedOut': True}

    def profile(self, owner, patch=None):
        with self.connect() as db:
            if patch is not None:
                def text(name, required, maximum):
                    value = patch.get(name, '')
                    if not isinstance(value, str):
                        fail(400, 'INVALID_PROFILE', f'Invalid {name}')
                    value = value.strip()
                    if (required and not value) or len(value) > maximum:
                        fail(400, 'INVALID_PROFILE', f'Invalid {name}')
                    return value
                first, last, email = text('firstName', True, 80), text('lastName', True, 80), text('email', False, 254)
                if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
                    fail(400, 'INVALID_EMAIL', 'Enter a valid email address or leave it blank')
                db.execute('UPDATE passengers SET first_name=?,last_name=?,email=?,updated_ms=? WHERE id=?',
                           (first, last, email.lower(), self.clock(), owner))
            row = db.execute('SELECT id,phone,first_name,last_name,email FROM passengers WHERE id=?', (owner,)).fetchone()
            if not row:
                fail(404, 'ACCOUNT_NOT_FOUND', 'Passenger account not found')
            return self.account_json(row)

    def connect(self):
        return connect(self.database)

    def ensure_default_payment(self, db, owner):
        """Seed a token-like development reference. No PAN, CVV or real payment credential is stored."""
        if not db.execute('SELECT 1 FROM passengers WHERE id=?', (owner,)).fetchone():
            return {'id': 'pm_development_4242', 'type': 'CARD', 'brand': 'Visa', 'last4': '4242',
                    'expiryMonth': 12, 'expiryYear': 2030, 'isDefault': True, 'developmentOnly': True}
        row = db.execute('SELECT id,type,brand,last4,expiry_month,expiry_year,is_default FROM payment_methods '
                         'WHERE passenger_id=? ORDER BY is_default DESC,created_ms LIMIT 1', (owner,)).fetchone()
        if not row:
            method_id = 'pm_' + secrets.token_hex(10)
            db.execute('INSERT INTO payment_methods VALUES (?,?,?,?,?,?,?,?,?)',
                       (method_id, owner, 'CARD', 'Visa', '4242', 12, 2030, 1, self.clock()))
            row = (method_id, 'CARD', 'Visa', '4242', 12, 2030, 1)
        return self.payment_json(row)

    @staticmethod
    def payment_json(row):
        return {'id': row[0], 'type': row[1], 'brand': row[2], 'last4': row[3],
                'expiryMonth': row[4], 'expiryYear': row[5], 'isDefault': bool(row[6]),
                'developmentOnly': True}

    def payment_methods(self, owner):
        with self.connect() as db:
            self.ensure_default_payment(db, owner)
            # Preserve the card's original position when the default changes. The
            # checkmark/highlight belongs to the selection, not the list order.
            rows = db.execute('SELECT id,type,brand,last4,expiry_month,expiry_year,is_default FROM payment_methods '
                              'WHERE passenger_id=? ORDER BY created_ms,id', (owner,)).fetchall()
            return {'paymentMethods': [self.payment_json(row) for row in rows], 'developmentOnly': True,
                    'notice': 'References only; no real card number, CVV or charge is stored'}

    def add_payment_method(self, owner, body):
        brand, last4 = body.get('brand'), body.get('last4')
        month, year = body.get('expiryMonth'), body.get('expiryYear')
        if brand not in ('Visa', 'Mastercard', 'Amex') or not isinstance(last4, str) or not re.fullmatch(r'\d{4}', last4):
            fail(400, 'INVALID_PAYMENT_METHOD', 'Choose a development card brand and four display digits')
        current_year = datetime.now(timezone.utc).year
        if type(month) is not int or not 1 <= month <= 12 or type(year) is not int or not current_year <= year <= current_year + 20:
            fail(400, 'INVALID_PAYMENT_EXPIRY', 'Enter a valid development expiry month and year')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            count = db.execute('SELECT COUNT(*) FROM payment_methods WHERE passenger_id=?', (owner,)).fetchone()[0]
            if count >= 5:
                fail(409, 'PAYMENT_METHOD_LIMIT', 'Remove a payment method before adding another')
            method_id, is_default = 'pm_' + secrets.token_hex(10), 1 if count == 0 else 0
            # Use a strictly increasing per-passenger timestamp so the visible order
            # remains the order added even when two cards arrive in the same millisecond.
            last_created = db.execute('SELECT MAX(created_ms) FROM payment_methods WHERE passenger_id=?',
                                      (owner,)).fetchone()[0]
            created_ms = max(self.clock(), (last_created or 0) + 1)
            db.execute('INSERT INTO payment_methods VALUES (?,?,?,?,?,?,?,?,?)',
                       (method_id, owner, 'CARD', brand, last4, month, year, is_default, created_ms))
            row = (method_id, 'CARD', brand, last4, month, year, is_default)
            return self.payment_json(row)

    def update_payment_method(self, owner, method_id, action):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT id,type,brand,last4,expiry_month,expiry_year,is_default FROM payment_methods '
                             'WHERE id=? AND passenger_id=?', (method_id, owner)).fetchone()
            if not row:
                fail(404, 'PAYMENT_METHOD_NOT_FOUND', 'Payment method not found')
            if action == 'default':
                db.execute('UPDATE payment_methods SET is_default=0 WHERE passenger_id=?', (owner,))
                db.execute('UPDATE payment_methods SET is_default=1 WHERE id=?', (method_id,))
                return {**self.payment_json(row), 'isDefault': True}
            count = db.execute('SELECT COUNT(*) FROM payment_methods WHERE passenger_id=?', (owner,)).fetchone()[0]
            if count <= 1:
                fail(409, 'LAST_PAYMENT_METHOD', 'Keep at least one development payment method')
            db.execute('DELETE FROM payment_methods WHERE id=?', (method_id,))
            if row[6]:
                replacement = db.execute('SELECT id FROM payment_methods WHERE passenger_id=? ORDER BY created_ms,id LIMIT 1', (owner,)).fetchone()
                db.execute('UPDATE payment_methods SET is_default=1 WHERE id=?', (replacement[0],))
            return {'removed': True, 'id': method_id}

    @staticmethod
    def place_identity(place):
        return (place.get('placeId') or place['address']).strip().lower()

    def account_places(self, owner):
        with self.connect() as db:
            saved = {row[0]: json.loads(row[1]) for row in db.execute(
                'SELECT slot,payload FROM saved_places WHERE passenger_id=?', (owner,))}
            recent = [json.loads(row[0]) for row in db.execute(
                'SELECT payload FROM recent_destinations WHERE passenger_id=? ORDER BY used_ms DESC LIMIT 8', (owner,))]
        return {'savedPlaces': saved, 'recentDestinations': recent}

    def change_saved_place(self, owner, body):
        slot, action = body.get('slot'), body.get('action', 'save')
        if slot not in ('home', 'work'):
            fail(400, 'INVALID_PLACE_SLOT', 'Saved place slot must be home or work')
        with self.connect() as db:
            if action == 'remove':
                db.execute('DELETE FROM saved_places WHERE passenger_id=? AND slot=?', (owner, slot))
                return {'slot': slot, 'removed': True}
            place = self.place(body.get('place'))
            if isinstance(body.get('place'), dict) and isinstance(body['place'].get('placeId'), str):
                place['placeId'] = body['place']['placeId'][:256]
            db.execute('INSERT INTO saved_places VALUES (?,?,?,?) ON CONFLICT(passenger_id,slot) '
                       'DO UPDATE SET payload=excluded.payload,updated_ms=excluded.updated_ms',
                       (owner, slot, json.dumps(place), self.clock()))
            return {'slot': slot, 'place': place}

    def change_recent_destination(self, owner, body):
        action = body.get('action', 'add')
        with self.connect() as db:
            if action == 'clear':
                db.execute('DELETE FROM recent_destinations WHERE passenger_id=?', (owner,))
            else:
                place = self.place(body.get('place'))
                if isinstance(body.get('place'), dict) and isinstance(body['place'].get('placeId'), str):
                    place['placeId'] = body['place']['placeId'][:256]
                identity = self.place_identity(place)
                if action == 'remove':
                    db.execute('DELETE FROM recent_destinations WHERE passenger_id=? AND identity=?', (owner, identity))
                elif action == 'add':
                    db.execute('INSERT INTO recent_destinations VALUES (?,?,?,?) ON CONFLICT(passenger_id,identity) '
                               'DO UPDATE SET payload=excluded.payload,used_ms=excluded.used_ms',
                               (owner, identity, json.dumps(place), self.clock()))
                    db.execute('DELETE FROM recent_destinations WHERE passenger_id=? AND identity NOT IN '
                               '(SELECT identity FROM recent_destinations WHERE passenger_id=? ORDER BY used_ms DESC LIMIT 8)',
                               (owner, owner))
                else:
                    fail(400, 'INVALID_RECENT_ACTION', 'Recent destination action is add, remove or clear')
        return self.account_places(owner)

    def resolve_payment(self, db, owner, method_id):
        fallback = self.ensure_default_payment(db, owner)
        if method_id is None:
            return fallback
        row = db.execute('SELECT id,type,brand,last4,expiry_month,expiry_year,is_default FROM payment_methods '
                         'WHERE id=? AND passenger_id=?', (method_id, owner)).fetchone()
        if not row:
            fail(422, 'PAYMENT_METHOD_UNAVAILABLE', 'Choose an available payment method')
        return self.payment_json(row)

    def place(self, value):
        if not isinstance(value, dict):
            fail(400, 'INVALID_PLACE', 'Pickup and destination coordinates are required')
        result = {}
        for key, limit in [('name', 160), ('address', 500)]:
            text = value.get(key)
            if not isinstance(text, str) or not text.strip() or len(text) > limit:
                fail(400, 'INVALID_PLACE', f'Invalid {key}')
            result[key] = text.strip()
        for key, lo, hi in [('latitude', -90, 90), ('longitude', -180, 180)]:
            number = value.get(key)
            if type(number) not in (int, float) or not math.isfinite(number) or not lo <= number <= hi:
                fail(400, 'INVALID_COORDINATES', 'Valid coordinates are required')
            result[key] = number
        # Deliberately small development area, NOT legal regional boundary data.
        south, north, west, east = self.config['developmentBounds']
        if not (south <= result['latitude'] <= north and west <= result['longitude'] <= east):
            fail(422, 'OUTSIDE_DEVELOPMENT_AREA', 'This development server supports the Vancouver/Langley test area only')
        return result

    def route(self, pickup, destination):
        key = os.environ.get('GOOGLE_ROUTES_API_KEY')
        if key:
            body = {
                'origin': {'location': {'latLng': pickup_coords(pickup)}},
                'destination': {'location': {'latLng': pickup_coords(destination)}},
                'travelMode': 'DRIVE', 'routingPreference': 'TRAFFIC_AWARE'
            }
            req = urllib.request.Request('https://routes.googleapis.com/directions/v2:computeRoutes',
                data=json.dumps(body).encode(), headers={
                    'Content-Type': 'application/json', 'X-Goog-Api-Key': key,
                    'X-Goog-FieldMask': 'routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline'})
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    route = json.load(response)['routes'][0]
                return {'distanceKm': route['distanceMeters'] / 1000,
                        'durationMinutes': math.ceil(float(route['duration'].rstrip('s')) / 60),
                        'routeType': 'BEST', 'isApproximate': False,
                        'path': decode_polyline(route.get('polyline', {}).get('encodedPolyline', ''))}
            except Exception:
                fail(503, 'ROUTING_UNAVAILABLE', 'Routing provider unavailable; no booking was created')
        # Development approximation computed on SERVER, never trust client fare/distance.
        lat1, lat2 = map(math.radians, [pickup['latitude'], destination['latitude']])
        dlat = lat2 - lat1
        dlon = math.radians(destination['longitude'] - pickup['longitude'])
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        km = max(0.1, 6371 * 2 * math.asin(min(1, math.sqrt(a))) * 1.3)
        return {'distanceKm': round(km, 2), 'durationMinutes': max(1, math.ceil(km / 30 * 60)),
                'routeType': 'BEST', 'isApproximate': True,
                'path': [pickup_coords(pickup), pickup_coords(destination)]}

    def selected_route(self, body, pickup, destination):
        """Validate a road route selected in the Android Google Routes UI.

        Build 40 keeps that exact selection through quoting instead of silently replacing it
        with the server's straight-line development fallback. This is deliberately strict and
        only accepts a non-approximate route with plausible geometry. Production still needs
        server-owned routing credentials and provider-side verification (Build 41).
        """
        route = body.get('route')
        if not isinstance(route, dict) or route.get('isApproximate') is not False:
            return None
        distance, duration = route.get('distanceKm'), route.get('durationMinutes')
        route_type, points = route.get('routeType'), route.get('path')
        if (type(distance) not in (int, float) or isinstance(distance, bool) or
                not math.isfinite(distance) or not 0.1 <= distance <= 1000 or
                type(duration) is not int or isinstance(duration, bool) or not 1 <= duration <= 1440 or
                route_type not in ('BEST', 'FASTEST', 'SHORTEST', 'POCKET', 'ALTERNATIVE') or
                not isinstance(points, list) or not 2 <= len(points) <= 5000):
            return None
        normalized = []
        south, north, west, east = self.config['developmentBounds']
        for point in points:
            if not isinstance(point, dict):
                return None
            latitude, longitude = point.get('latitude'), point.get('longitude')
            if (type(latitude) not in (int, float) or isinstance(latitude, bool) or
                    type(longitude) not in (int, float) or isinstance(longitude, bool) or
                    not math.isfinite(latitude) or not math.isfinite(longitude) or
                    not south <= latitude <= north or not west <= longitude <= east):
                return None
            normalized.append({'latitude': float(latitude), 'longitude': float(longitude)})
        start = normalized[0]
        end = normalized[-1]
        if (self.distance_km(start['latitude'], start['longitude'], pickup['latitude'], pickup['longitude']) > 2 or
                self.distance_km(end['latitude'], end['longitude'], destination['latitude'], destination['longitude']) > 2):
            return None
        direct = self.distance_km(pickup['latitude'], pickup['longitude'],
                                  destination['latitude'], destination['longitude'])
        geometry = sum(self.distance_km(a['latitude'], a['longitude'], b['latitude'], b['longitude'])
                       for a, b in zip(normalized, normalized[1:]))
        if (distance < max(0.1, direct * 0.95) or distance > max(direct * 4.5, direct + 30) or
                geometry < distance * 0.75 or geometry > distance * 1.25 or
                not 0.25 <= duration / distance <= 15):
            return None
        return {'distanceKm': round(float(distance), 3), 'durationMinutes': duration,
                'routeType': route_type, 'isApproximate': False, 'path': normalized,
                'routeSource': 'SELECTED_GOOGLE_ROUTE'}

    def price(self, tier, route):
        rate = self.config['tiers'][tier]
        raw = (Decimal(rate['baseCents']) + Decimal(str(route['distanceKm'])) * rate['perKmCents']
               + Decimal(str(route['durationMinutes'])) * rate['perMinuteCents'])
        subtotal = max(rate['minimumSubtotalCents'], cents(raw))
        tax = cents(Decimal(subtotal) * self.config['gstBasisPoints'] / 10000)
        total = max(subtotal + tax, self.config['regulatoryMinimumTotalCents'])
        # The regulatory floor is GST-inclusive; do not add GST to it twice.
        tax = cents(Decimal(total) * self.config['gstBasisPoints'] / (10000 + self.config['gstBasisPoints']))
        subtotal = total - tax
        commission = cents(Decimal(subtotal) * self.config['commissionBasisPoints'] / 10000)
        return {'tier': tier, 'title': rate['title'], 'description': 'Development quote · GST included',
                'etaMinutes': 0, 'fareCad': total / 100, 'seats': rate['seats'],
                'breakdown': {'currency': 'CAD', 'subtotalCents': subtotal, 'gstCents': tax,
                    'totalCents': total, 'platformCommissionCents': commission,
                    'driverGrossBeforeCostsCents': subtotal - commission,
                    'note': 'Illustrative allocation, not a payout or driver net earnings; excludes costs and tax settlement'}}

    def schedule(self, body, min_lead=True):
        scheduled = body.get('scheduled', False)
        if type(scheduled) is not bool:
            fail(400, 'INVALID_SCHEDULE', 'scheduled must be a boolean')
        at = body.get('scheduledAtEpochMs')
        if not scheduled:
            if at is not None:
                fail(400, 'INVALID_SCHEDULE', 'Ride Now must not contain a scheduled timestamp')
            return {'scheduled': False, 'scheduleLabel': 'Now'}
        zone = body.get('scheduleTimeZone')
        if type(at) is not int or not isinstance(zone, str) or not 1 <= len(zone) <= 80 or not all(c.isalnum() or c in '/_+-:.' for c in zone):
            fail(400, 'INVALID_SCHEDULE', 'A UTC epoch-millisecond timestamp and display time-zone ID are required')
        lead = self.config['scheduleMinLeadMinutes'] * 60000 if min_lead else 0
        if at < self.clock() + lead or at > self.clock() + self.config['scheduleMaxDays'] * 86400000:
            fail(422, 'SCHEDULE_OUT_OF_RANGE', 'Choose a pickup 15 minutes to 30 days from now')
        # UTC is authoritative. Zone is display metadata, never interpreted to shift the instant.
        return {'scheduled': True, 'scheduledAtEpochMs': at, 'scheduleTimeZone': zone,
                'scheduleLabel': datetime.fromtimestamp(at / 1000, timezone.utc).strftime('%d %b %Y · %H:%M UTC')}

    def passenger_availability(self, body):
        pickup = self.place(body.get('pickup'))
        tier = body.get('tier')
        if not isinstance(tier, str) or tier not in self.config['tiers']:
            fail(400, 'INVALID_TIER', 'Choose a valid ride category')
        fleet_available = self.fleet.passenger_availability(pickup, tier)
        if fleet_available: return fleet_available
        with self.connect() as db:
            state = db.execute('SELECT online FROM driver_state WHERE id=1').fetchone()
            if not state or not state[0] or self.driver_active(db):
                return {'available': False, 'etaMinutes': None, 'distanceKm': None, 'locationAgeSeconds': None}
            presence = db.execute('SELECT latitude,longitude,recorded_ms FROM driver_presence WHERE id=1').fetchone()
            if not presence:
                return {'available': False, 'etaMinutes': None, 'distanceKm': None, 'locationAgeSeconds': None}
            age_ms = max(0, self.clock() - presence[2])
            if age_ms > 30000:
                return {'available': False, 'etaMinutes': None, 'distanceKm': None, 'locationAgeSeconds': int(age_ms / 1000)}
            distance = self.distance_km(presence[0], presence[1], pickup['latitude'], pickup['longitude'])
            # Near-zero distance means the driver is already effectively at the pickup.
            if distance <= 0.20:
                eta = 1
            else:
                eta = max(1, int(math.ceil((distance / 28.0) * 60.0 + 1.0)))
            return {'available': True, 'etaMinutes': eta, 'distanceKm': round(distance, 2),
                    'locationAgeSeconds': int(age_ms / 1000)}

    def quote(self, owner, body):
        schedule = self.schedule(body)
        pickup, destination = self.place(body.get('pickup')), self.place(body.get('destination'))
        selected = self.selected_route(body, pickup, destination)
        route = selected or self.route_provider(pickup, destination)
        supplied = isinstance(body.get('route'), dict)
        route_changed = supplied and selected is None
        token = secrets.token_urlsafe(32)
        response = {'quoteToken': token, 'expiresAtEpochMs': self.clock() + self.config['quoteTtlSeconds'] * 1000,
                    'currency': 'CAD', 'options': [self.price(t, route) for t in self.config['tiers']],
                    'route': route, 'routeChanged': route_changed,
                    'routeChangeReason': ('Selected route could not be verified; review the server route before booking'
                                          if route_changed else None),
                    'developmentOnly': True,
                    'cancellationPolicy': {'graceSeconds': self.config['graceSeconds'],
                        'feeCents': self.config['cancellationFeeCents']},
                    'pricingVersion': self.config['version'], **schedule,
                    'schedulePolicy': {'minimumLeadMinutes': self.config['scheduleMinLeadMinutes'],
                        'maximumDays': self.config['scheduleMaxDays'], 'freeCancellationWhileScheduled': True}}
        payload = {**response, 'pickup': pickup, 'destination': destination}
        with self.connect() as db:
            db.execute('INSERT INTO quotes VALUES (?,?,?,?,NULL)',
                       (token, owner, response['expiresAtEpochMs'], json.dumps(payload)))
        return response

    def event(self, db, ride, actor, event_type):
        db.execute('INSERT INTO events(ride_id,at_ms,actor,type,payload) VALUES (?,?,?,?,?)',
                   (ride['id'], self.clock(), actor, event_type,
                    json.dumps({'status': ride['status'], 'cancellationFeeCad': ride['cancellationFeeCad'],
                                'scheduledAtEpochMs': ride['draft'].get('scheduledAtEpochMs')})))

    def create(self, owner, body):
        token = body.get('quoteToken')
        tier = body.get('rideOption', {}).get('tier') if isinstance(body.get('rideOption'), dict) else None
        if not isinstance(token, str) or not isinstance(tier, str) or tier not in self.config['tiers']:
            fail(400, 'QUOTE_REQUIRED', 'A quote token and valid ride tier are required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            payment_method = self.resolve_payment(db, owner, body.get('paymentMethodId'))
            row = db.execute('SELECT expires,payload,ride_id FROM quotes WHERE token=? AND owner=?', (token, owner)).fetchone()
            if not row:
                fail(404, 'QUOTE_NOT_FOUND', 'Quote not found')
            if row[2]:
                ride = self.get(owner, row[2], db)
                if ride['option']['tier'] != tier:
                    fail(409, 'QUOTE_ALREADY_USED', 'This quote already booked a different ride tier')
                return ride  # Replaying a timed-out request cannot book twice.
            if self.clock() >= row[0]:
                fail(409, 'QUOTE_EXPIRED', 'Quote expired. Get a new fare before booking')
            quote = json.loads(row[1])
            schedule = self.schedule(quote, min_lead=False)
            active = [json.loads(r[0]) for r in db.execute('SELECT payload FROM rides WHERE owner=?', (owner,))]
            if not schedule['scheduled'] and any(r['status'] in LIVE_STATES for r in active):
                fail(409, 'ACTIVE_RIDE_EXISTS', 'You already have an active ride. Open Trips')
            upcoming = [r for r in active if r['status'] == 'SCHEDULED']
            if schedule['scheduled']:
                if len(upcoming) >= self.config['maxScheduledRides']:
                    fail(409, 'SCHEDULE_LIMIT', 'Too many upcoming rides. Cancel one before booking another')
                if any(abs(schedule['scheduledAtEpochMs'] - r['draft'].get('scheduledAtEpochMs', 0)) < self.config['scheduleGapMinutes'] * 60000 for r in upcoming):
                    fail(409, 'SCHEDULE_CONFLICT', 'Keep at least 60 minutes between scheduled pickups')
            now = self.clock()
            policy = quote['cancellationPolicy']
            ride = {'id': 'rn_' + secrets.token_hex(12), 'draft': {'pickup': quote['pickup'],
                    'destination': quote['destination'], 'routeEstimate': quote['route'],
                    'selectedTier': tier, **schedule},
                    'option': next(o for o in quote['options'] if o['tier'] == tier),
                    'status': 'SCHEDULED' if schedule['scheduled'] else 'SEARCHING', 'requestedAtEpochMs': now, 'updatedAtEpochMs': now,
                    'graceEndsAtEpochMs': now + policy['graceSeconds'] * 1000,
                    'graceSeconds': policy['graceSeconds'],
                    'cancellationFeeCad': 0, 'cancellationFeeAfterGraceCad': policy['feeCents'] / 100,
                    'payment': {'methodId': payment_method['id'], 'type': payment_method['type'],
                        'brand': payment_method['brand'], 'last4': payment_method['last4'],
                        'status': 'NOT_CHARGED', 'amountCents': 0, 'developmentOnly': True},
                    'pricingVersion': quote['pricingVersion'], 'developmentOnly': True}
            db.execute('INSERT INTO rides VALUES (?,?,?)', (ride['id'], owner, json.dumps(ride)))
            db.execute('UPDATE quotes SET ride_id=? WHERE token=?', (ride['id'], token))
            self.event(db, ride, owner, 'RIDE_SCHEDULED' if schedule['scheduled'] else 'RIDE_REQUESTED')
            return ride

    def get(self, owner, ride_id, db=None):
        if db is None:
            with self.connect() as connection:
                return self.get(owner, ride_id, connection)
        row = db.execute('SELECT payload FROM rides WHERE id=? AND owner=?', (ride_id, owner)).fetchone()
        if not row:
            fail(404, 'RIDE_NOT_FOUND', 'Ride not found')
        return json.loads(row[0])

    def list(self, owner):
        with self.connect() as db:
            rides = [json.loads(r[0]) for r in db.execute('SELECT payload FROM rides WHERE owner=?', (owner,))]
        return {'rides': sorted(rides, key=lambda r: r['requestedAtEpochMs'], reverse=True)}

    def cancel(self, owner, ride_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            ride = self.get(owner, ride_id, db)
            if ride['status'] == 'CANCELLED_BY_RIDER':
                return ride
            if ride['status'] not in ('SCHEDULED', 'SEARCHING', 'DRIVER_ASSIGNED', 'DRIVER_ARRIVED'):
                fail(409, 'INVALID_TRANSITION', 'This ride cannot be cancelled')
            free = ride['status'] == 'SCHEDULED' or self.clock() <= ride['graceEndsAtEpochMs']
            ride.update(status='CANCELLED_BY_RIDER', updatedAtEpochMs=self.clock(),
                cancellationFeeCad=0 if free else ride['cancellationFeeAfterGraceCad'])
            ride.setdefault('payment', {}).update(
                status='VOIDED' if free else 'CAPTURED_DEMO',
                amountCents=0 if free else cents(ride['cancellationFeeCad'] * 100))
            db.execute('UPDATE rides SET payload=? WHERE id=?', (json.dumps(ride), ride_id))
            self.event(db, ride, owner, 'RIDER_CANCELLED')
            return ride

    def activate_due(self):
        """Atomic, restart-safe tick. Never starts a second live trip for the owner."""
        changed = []
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = [(owner, json.loads(payload)) for owner, payload in db.execute('SELECT owner,payload FROM rides')]
            busy = {owner for owner, r in rows if r['status'] in LIVE_STATES}
            for owner, ride in sorted(rows, key=lambda item: item[1]['draft'].get('scheduledAtEpochMs', 0) or 0):
                at = ride['draft'].get('scheduledAtEpochMs')
                if ride['status'] != 'SCHEDULED' or type(at) is not int or at > self.clock():
                    continue
                if self.clock() > at + self.config['scheduleLateMinutes'] * 60000:
                    ride['status'] = 'SCHEDULE_EXPIRED'
                    ride.setdefault('payment', {}).update(status='VOIDED', amountCents=0)
                    kind = 'SCHEDULE_EXPIRED'
                elif owner in busy:
                    continue
                else:
                    ride['status'] = 'SEARCHING'
                    ride['graceEndsAtEpochMs'] = self.clock() + ride.get('graceSeconds', 120) * 1000
                    busy.add(owner)
                    kind = 'SCHEDULE_ACTIVATED'
                ride['updatedAtEpochMs'] = self.clock()
                db.execute('UPDATE rides SET payload=? WHERE id=?', (json.dumps(ride), ride['id']))
                self.event(db, ride, 'scheduler', kind)
                changed.append(ride['id'])
        return changed

    def transition(self, ride_id, target):
        allowed = {'SEARCHING': 'DRIVER_ASSIGNED', 'DRIVER_ASSIGNED': 'DRIVER_ARRIVED',
                   'DRIVER_ARRIVED': 'TRIP_STARTED', 'TRIP_STARTED': 'COMPLETED'}
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM rides WHERE id=?', (ride_id,)).fetchone()
            if not row:
                fail(404, 'RIDE_NOT_FOUND', 'Ride not found')
            ride = json.loads(row[0])
            if allowed.get(ride['status']) != target:
                fail(409, 'INVALID_TRANSITION', 'Trip states must advance in order')
            ride.update(status=target, updatedAtEpochMs=self.clock())
            if target == 'DRIVER_ASSIGNED':
                ride['driver'] = {'name': 'Development driver', 'rating': 5.0, 'vehicle': 'Test vehicle',
                                  'colour': 'Test', 'plate': 'DEMO', 'pickupEtaMinutes': 3}
                ride['pin'] = str(secrets.randbelow(9000) + 1000)
            elif target == 'COMPLETED':
                ride.setdefault('payment', {}).update(status='CAPTURED_DEMO',
                    amountCents=ride.get('option', {}).get('breakdown', {}).get('totalCents', cents(ride['option']['fareCad'] * 100)))
            db.execute('UPDATE rides SET payload=? WHERE id=?', (json.dumps(ride), ride_id))
            self.event(db, ride, 'development-admin', 'STATUS_CHANGED')
            return ride

    def report_driver_position(self, ride_id, body):
        # Development-admin input only. A driver app must use its own authenticated API later.
        lat, lng = body.get('latitude'), body.get('longitude')
        if (isinstance(lat, bool) or isinstance(lng, bool) or
                not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)) or
                not math.isfinite(lat) or not math.isfinite(lng) or
                not -90 <= lat <= 90 or not -180 <= lng <= 180):
            fail(400, 'INVALID_POSITION', 'Provide valid latitude and longitude')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM rides WHERE id=?', (ride_id,)).fetchone()
            if not row:
                fail(404, 'RIDE_NOT_FOUND', 'Ride not found')
            ride = json.loads(row[0])
            if ride['status'] not in ('DRIVER_ASSIGNED', 'DRIVER_ARRIVED', 'TRIP_STARTED'):
                fail(409, 'INVALID_TRANSITION', 'Driver position requires an assigned active ride')
            at = self.clock()
            ride['driverPosition'] = {'latitude': float(lat), 'longitude': float(lng), 'recordedAtEpochMs': at}
            ride['updatedAtEpochMs'] = at
            db.execute('UPDATE rides SET payload=? WHERE id=?', (json.dumps(ride), ride_id))
            self.event(db, ride, 'development-admin', 'DRIVER_POSITION_REPORTED')
            return ride

    def driver_availability(self, body):
        online = body.get('online')
        if type(online) is not bool:
            fail(400, 'INVALID_AVAILABILITY', 'online must be a boolean')
        fields = []
        for key in ('name', 'vehicle', 'plate'):
            value = body.get(key, '')
            if not isinstance(value, str) or len(value.strip()) > 80:
                fail(400, 'INVALID_PROFILE', f'Invalid driver {key}')
            fields.append(value.strip())
        with self.connect() as db:
            db.execute('INSERT INTO driver_state(id,online,name,vehicle,plate) VALUES (1,?,?,?,?) '
                       'ON CONFLICT(id) DO UPDATE SET online=excluded.online,name=excluded.name,'
                       'vehicle=excluded.vehicle,plate=excluded.plate', (int(online), *fields))
            if not online:
                db.execute('DELETE FROM driver_offer_state WHERE id=1')
        return {'online': online}

    def driver_presence(self, body):
        lat, lng = body.get('latitude'), body.get('longitude')
        if any(type(v) not in (float, int) or not math.isfinite(v) for v in (lat, lng)) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
            fail(400, 'INVALID_POSITION', 'Provide valid latitude and longitude')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = db.execute('SELECT online FROM driver_state WHERE id=1').fetchone()
            if not state or not state[0]:
                fail(409, 'DRIVER_OFFLINE', 'Go online before publishing location')
            recorded = self.clock()
            db.execute('INSERT INTO driver_presence(id,latitude,longitude,recorded_ms) VALUES (1,?,?,?) '
                       'ON CONFLICT(id) DO UPDATE SET latitude=excluded.latitude,longitude=excluded.longitude,'
                       'recorded_ms=excluded.recorded_ms', (float(lat), float(lng), recorded))

            # Build 23: the driver's general online presence is also the authoritative live
            # position for an assigned ride. This lets the foreground location service keep
            # the passenger map moving even when the Driver activity is backgrounded.
            active = self.driver_active(db)
            response = {'latitude': float(lat), 'longitude': float(lng), 'recordedAtEpochMs': recorded}
            if active:
                active['driverPosition'] = {'latitude': float(lat), 'longitude': float(lng),
                                            'recordedAtEpochMs': recorded}
                active['updatedAtEpochMs'] = recorded
                response['activeRideId'] = active['id']
                response['rideStatus'] = active['status']
                if active['status'] == 'DRIVER_ASSIGNED':
                    pickup = pickup_coords(active['draft']['pickup'])
                    distance = self.distance_km(float(lat), float(lng), pickup['latitude'], pickup['longitude'])
                    eta = 1 if distance <= 0.15 else max(2, int(math.ceil((distance / 28.0) * 60.0 + 1.0)))
                    active.setdefault('driver', {})['pickupEtaMinutes'] = eta
                    active.setdefault('dispatch', {})['livePickupDistanceKm'] = round(distance, 2)
                    active['dispatch']['livePickupEtaMinutes'] = eta
                    response['distanceToNextStopKm'] = round(distance, 2)
                    response['etaToNextStopMinutes'] = eta
                elif active['status'] == 'TRIP_STARTED':
                    destination = pickup_coords(active['draft']['destination'])
                    distance = self.distance_km(float(lat), float(lng), destination['latitude'], destination['longitude'])
                    eta = max(1, int(math.ceil((distance / 36.0) * 60.0)))
                    route_km = max(0.1, float(active['draft'].get('routeEstimate', {}).get('distanceKm', distance)))
                    progress = max(0.0, min(1.0, 1.0 - distance / route_km))
                    active['liveTrip'] = {'remainingDistanceKm': round(distance, 2),
                                          'remainingEtaMinutes': eta,
                                          'progress': round(progress, 3),
                                          'updatedAtEpochMs': recorded}
                    response['distanceToNextStopKm'] = round(distance, 2)
                    response['etaToNextStopMinutes'] = eta
                    response['progress'] = round(progress, 3)
                db.execute('UPDATE rides SET payload=? WHERE id=?', (json.dumps(active), active['id']))
            return response

    def driver_status(self):
        with self.connect() as db:
            state = db.execute('SELECT online,name,vehicle,plate FROM driver_state WHERE id=1').fetchone()
            presence = db.execute('SELECT latitude,longitude,recorded_ms FROM driver_presence WHERE id=1').fetchone()
            active = self.driver_active(db)
            result = {
                'online': bool(state and state[0]),
                'name': (state[1] if state else '') or 'Driver',
                'vehicle': (state[2] if state else '') or 'Add your vehicle',
                'plate': (state[3] if state else '') or 'Not set',
                'activeRideId': active.get('id') if active else None,
                'activeRideStatus': active.get('status') if active else None,
            }
            if presence:
                result['lastLocation'] = {'latitude': presence[0], 'longitude': presence[1],
                                          'recordedAtEpochMs': presence[2],
                                          'ageSeconds': max(0, int((self.clock() - presence[2]) / 1000))}
            return result

    @staticmethod
    def distance_km(a_lat, a_lng, b_lat, b_lng):
        radius = 6371.0088
        p1, p2 = math.radians(a_lat), math.radians(b_lat)
        dp = math.radians(b_lat - a_lat)
        dl = math.radians(b_lng - a_lng)
        h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return radius * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))

    def pickup_metrics(self, db, pickup):
        presence = db.execute('SELECT latitude,longitude,recorded_ms FROM driver_presence WHERE id=1').fetchone()
        if not presence or self.clock() - presence[2] > 120000:
            return 0.0, 5
        distance = self.distance_km(presence[0], presence[1], pickup['latitude'], pickup['longitude'])
        # Conservative city-driving approximation for development dispatch until routing ETA is server-side.
        eta = max(1, int(math.ceil((distance / 28.0) * 60.0 + 1.0)))
        return round(distance, 2), eta

    @staticmethod
    def driver_active(db):
        for (payload,) in db.execute('SELECT payload FROM rides'):
            ride = json.loads(payload)
            if ride.get('driverSession') == 'development-driver' and ride['status'] in (
                    'DRIVER_ASSIGNED', 'DRIVER_ARRIVED', 'TRIP_STARTED'):
                return ride
        return {}

    def driver_offer(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = db.execute('SELECT online FROM driver_state WHERE id=1').fetchone()
            if not state or not state[0] or self.driver_active(db):
                db.execute('DELETE FROM driver_offer_state WHERE id=1')
                return {}
            now = self.clock()
            current = db.execute('SELECT ride_id,expires_ms FROM driver_offer_state WHERE id=1').fetchone()
            ride = None
            expires = None
            if current:
                row = db.execute('SELECT payload FROM rides WHERE id=?', (current[0],)).fetchone()
                candidate = json.loads(row[0]) if row else None
                if candidate and candidate.get('status') == 'SEARCHING' and current[1] > now:
                    ride, expires = candidate, current[1]
                else:
                    if candidate and candidate.get('status') == 'SEARCHING' and current[1] <= now:
                        db.execute('INSERT INTO driver_declines(ride_id,until_ms) VALUES (?,?) '
                                   'ON CONFLICT(ride_id) DO UPDATE SET until_ms=excluded.until_ms',
                                   (current[0], now + 20000))
                    db.execute('DELETE FROM driver_offer_state WHERE id=1')
            if ride is None:
                declined = {r[0] for r in db.execute('SELECT ride_id FROM driver_declines WHERE until_ms>?', (now,))}
                declined.update(r[0] for r in db.execute('SELECT ride_id FROM fleet_offers WHERE expires_ms>?', (now,)))
                declined.update(r[0] for r in db.execute('SELECT ride_id FROM fleet_radar WHERE status="OPEN" AND expires_ms>?', (now,)))
                candidates = [json.loads(r[0]) for r in db.execute('SELECT payload FROM rides')]
                available = sorted((r for r in candidates if r['status'] == 'SEARCHING' and r['id'] not in declined),
                                   key=lambda r: r['requestedAtEpochMs'])
                if not available:
                    return {}
                ride = available[0]
                expires = now + 20000
                db.execute('INSERT INTO driver_offer_state(id,ride_id,expires_ms) VALUES (1,?,?) '
                           'ON CONFLICT(id) DO UPDATE SET ride_id=excluded.ride_id,expires_ms=excluded.expires_ms',
                           (ride['id'], expires))
            draft, option = ride['draft'], ride['option']
            owner = db.execute('SELECT first_name FROM passengers WHERE id=(SELECT owner FROM rides WHERE id=?)',
                               (ride['id'],)).fetchone()
            pickup_distance, pickup_eta = self.pickup_metrics(db, pickup_coords(draft['pickup']))
            return {'id': ride['id'], 'riderName': owner[0] if owner and owner[0] else 'Passenger',
                    'pickupName': draft['pickup']['name'], 'pickup': pickup_coords(draft['pickup']),
                    'destinationName': draft['destination']['name'], 'destination': pickup_coords(draft['destination']),
                    'pickupDistanceKm': pickup_distance, 'pickupEtaMin': pickup_eta,
                    'tripDistanceKm': draft['routeEstimate']['distanceKm'],
                    'tripEtaMin': draft['routeEstimate']['durationMinutes'],
                    'fareCad': option['fareCad'],
                    'driverEstimatedEarningsCad': option['breakdown']['driverGrossBeforeCostsCents'] / 100,
                    'category': option['title'], 'expiresAtEpochMs': expires}

    def driver_ride(self):
        with self.connect() as db:
            ride = self.driver_active(db)
            if ride:
                ride.pop('pin', None)  # PIN is supplied by the passenger, never shown in the driver app.
            return ride

    def record_development_earning(self, db, ride):
        """An immutable, idempotent development snapshot. Not a payout or tax assessment."""
        b = ride['option']['breakdown']
        db.execute('''INSERT OR IGNORE INTO development_earnings
            (ride_id,completed_ms,fare_subtotal_cents,gst_cents,passenger_total_cents,
             platform_commission_cents,driver_gross_before_costs_cents)
            VALUES (?,?,?,?,?,?,?)''', (
            ride['id'], self.clock(), b['subtotalCents'], b['gstCents'], b['totalCents'],
            b['platformCommissionCents'], b['driverGrossBeforeCostsCents']))

    def admin_overview(self):
        """Read-only development operations: do not expose phone numbers or PINs."""
        with self.connect() as db:
            rides = [json.loads(row[0]) for row in db.execute('SELECT payload FROM rides')]
            ledger = [dict(zip(('rideId','completedAtEpochMs','subtotalCents','gstCents',
                                'totalCents','commissionCents','driverGrossBeforeCostsCents'), row))
                      for row in db.execute('SELECT ride_id,completed_ms,fare_subtotal_cents,gst_cents,passenger_total_cents,platform_commission_cents,driver_gross_before_costs_cents FROM development_earnings ORDER BY completed_ms DESC LIMIT 200')]
            trip_list = [{'id':r['id'], 'status':r.get('status'),
                          'category':r.get('option',{}).get('title',''),
                          'driverId':r.get('fleetDriverId'), 'driverName':(r.get('driver') or {}).get('name'),
                          'pickup':self.fleet.label(r.get('draft',{}).get('pickup',{})),
                          'destination':self.fleet.label(r.get('draft',{}).get('destination',{})),
                          'updatedAtEpochMs':r.get('updatedAtEpochMs',0),
                          'fareCents':r.get('option',{}).get('breakdown',{}).get('totalCents',0)}
                         for r in rides]
            trip_list.sort(key=lambda r:r['updatedAtEpochMs'],reverse=True)
            totals={key:sum(entry[key] for entry in ledger) for key in
                    ('subtotalCents','gstCents','totalCents','commissionCents','driverGrossBeforeCostsCents')}
            return {'developmentOnly':True,'paymentProcessorConnected':False,
                    'taxTreatmentFinalized':False, 'passengerCount':db.execute('SELECT COUNT(*) FROM passengers').fetchone()[0],
                    'driver':self.driver_status(), 'fleetDrivers':self.fleet.list_drivers()['drivers'],
                    'driverStatusSource':'fleet', 'rideCount':len(rides),
                    'activeCount':sum(r.get('status') in LIVE_STATES for r in rides),
                    'completedCount':sum(r.get('status')=='COMPLETED' for r in rides),
                    'cancelledCount':sum(r.get('status','').startswith('CANCELLED') for r in rides),
                    'rides':trip_list[:200], 'ledger':ledger, 'totals':totals,
                    'experience':self.experience.dashboard()}

    def driver_history(self):
        with self.connect() as db:
            trips = []
            for (payload,) in db.execute('SELECT payload FROM rides'):
                ride = json.loads(payload)
                if ride.get('driverSession') != 'development-driver' or ride.get('status') != 'COMPLETED':
                    continue
                draft = ride.get('draft', {})
                route = draft.get('routeEstimate', {})
                option = ride.get('option', {})
                breakdown = option.get('breakdown', {})
                trips.append({
                    'id': ride.get('id', ''),
                    'pickup': draft.get('pickup', {}).get('name', 'Pickup'),
                    'destination': draft.get('destination', {}).get('name', 'Destination'),
                    'completedAtEpochMs': ride.get('updatedAtEpochMs', 0),
                    'grossFareCad': option.get('fareCad', 0.0),
                    'driverEarningsCad': breakdown.get('driverGrossBeforeCostsCents', 0) / 100,
                    'distanceKm': route.get('distanceKm', 0.0),
                    'durationMin': route.get('durationMinutes', 0),
                })
            trips.sort(key=lambda item: item['completedAtEpochMs'], reverse=True)
            return {'trips': trips}

    def driver_action(self, ride_id, action, body):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', ride_id):
            fail(404, 'RIDE_NOT_FOUND', 'Ride not found')
        if action not in ('accept', 'decline', 'arrive', 'start', 'complete', 'cancel', 'location'):
            fail(404, 'NOT_FOUND', 'Endpoint not found')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM rides WHERE id=?', (ride_id,)).fetchone()
            if not row:
                fail(404, 'RIDE_NOT_FOUND', 'Ride not found')
            ride = json.loads(row[0])
            # Build 40: network loss may hide a successful response from the driver.
            # Replaying an already-applied action must not add another event or earning.
            # Only the driver assigned to this ride can recover an action result.
            if ride.get('driverSession') == 'development-driver':
                already_applied = {
                    'accept': ('DRIVER_ASSIGNED', 'DRIVER_ARRIVED', 'TRIP_STARTED', 'COMPLETED'),
                    'arrive': ('DRIVER_ARRIVED', 'TRIP_STARTED', 'COMPLETED'),
                    'start': ('TRIP_STARTED', 'COMPLETED'),
                    'complete': ('COMPLETED',),
                }
                if action in already_applied and ride['status'] in already_applied[action]:
                    result = dict(ride)
                    result.pop('pin', None)
                    return result
            state = db.execute('SELECT online,name,vehicle,plate FROM driver_state WHERE id=1').fetchone()
            if action in ('accept', 'decline'):
                if not state or not state[0]:
                    fail(409, 'DRIVER_OFFLINE', 'Go online before responding to a request')
                if ride['status'] != 'SEARCHING':
                    fail(409, 'INVALID_TRANSITION', 'This request is no longer available')
                if action == 'accept':
                    if self.driver_active(db):
                        fail(409, 'DRIVER_BUSY', 'Complete the active ride first')
                    offer = db.execute('SELECT ride_id,expires_ms FROM driver_offer_state WHERE id=1').fetchone()
                    if not offer or offer[0] != ride_id:
                        fail(409, 'OFFER_NOT_ACTIVE', 'This request is no longer offered to this driver')
                    if offer[1] <= self.clock():
                        db.execute('DELETE FROM driver_offer_state WHERE id=1')
                        fail(409, 'OFFER_EXPIRED', 'This ride request expired')
                    until = db.execute('SELECT until_ms FROM driver_declines WHERE ride_id=?', (ride_id,)).fetchone()
                    if until and until[0] > self.clock():
                        fail(409, 'REQUEST_DECLINED', 'This ride is temporarily declined')
                    pickup_distance, pickup_eta = self.pickup_metrics(db, pickup_coords(ride['draft']['pickup']))
                    ride.update(status='DRIVER_ASSIGNED', driverSession='development-driver')
                    ride['driver'] = {'name': state[1] or 'Development driver', 'rating': 5.0,
                                      'vehicle': state[2] or 'Test vehicle', 'colour': '',
                                      'plate': state[3] or 'DEMO', 'pickupEtaMinutes': pickup_eta}
                    ride['dispatch'] = {'pickupDistanceKm': pickup_distance, 'pickupEtaMinutes': pickup_eta,
                                        'assignedAtEpochMs': self.clock()}
                    ride['pin'] = str(secrets.randbelow(9000) + 1000)
                    db.execute('DELETE FROM driver_offer_state WHERE id=1')
                else:
                    db.execute('DELETE FROM driver_offer_state WHERE id=1 AND ride_id=?', (ride_id,))
                    db.execute('INSERT INTO driver_declines(ride_id,until_ms) VALUES (?,?) '
                               'ON CONFLICT(ride_id) DO UPDATE SET until_ms=excluded.until_ms',
                               (ride_id, self.clock() + 60000))
                    return {'status': 'DECLINED'}
            else:
                if ride.get('driverSession') != 'development-driver':
                    fail(403, 'FORBIDDEN', 'Ride is not assigned to this driver')
                expected = {'arrive': 'DRIVER_ASSIGNED', 'start': 'DRIVER_ARRIVED',
                            'complete': 'TRIP_STARTED'}
                if action == 'location':
                    if ride['status'] not in ('DRIVER_ASSIGNED', 'DRIVER_ARRIVED', 'TRIP_STARTED'):
                        fail(409, 'INVALID_TRANSITION', 'Ride is no longer active')
                    lat, lng = body.get('latitude'), body.get('longitude')
                    if any(type(v) not in (float, int) or not math.isfinite(v) for v in (lat, lng)) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
                        fail(400, 'INVALID_POSITION', 'Provide valid latitude and longitude')
                    ride['driverPosition'] = {'latitude': float(lat), 'longitude': float(lng),
                                              'recordedAtEpochMs': self.clock()}
                else:
                    if (action == 'cancel' and ride['status'] not in ('DRIVER_ASSIGNED', 'DRIVER_ARRIVED')) or (
                            action != 'cancel' and ride['status'] != expected[action]):
                        fail(409, 'INVALID_TRANSITION', 'Trip states must advance in order')
                    if action == 'start' and (not isinstance(body.get('pin'), str) or
                                               not secrets.compare_digest(body['pin'], ride['pin'])):
                        fail(403, 'INVALID_PIN', 'Ask the passenger for the trip PIN')
                    if action == 'cancel':
                        ride.update(status='SEARCHING')
                        ride.pop('driver', None)
                        ride.pop('driverSession', None)
                        ride.pop('pin', None)
                        ride.pop('driverPosition', None)
                        db.execute('INSERT INTO driver_declines(ride_id,until_ms) VALUES (?,?) '
                                   'ON CONFLICT(ride_id) DO UPDATE SET until_ms=excluded.until_ms',
                                   (ride_id, self.clock() + 60000))
                    else:
                        ride['status'] = {'arrive': 'DRIVER_ARRIVED', 'start': 'TRIP_STARTED',
                                          'complete': 'COMPLETED'}[action]
                        if action == 'complete':
                            ride['payment'].update(status='CAPTURED_DEMO',
                                                   amountCents=ride['option']['breakdown']['totalCents'])
                            self.record_development_earning(db, ride)
            ride['updatedAtEpochMs'] = self.clock()
            db.execute('UPDATE rides SET payload=? WHERE id=?', (json.dumps(ride), ride_id))
            self.event(db, ride, 'development-driver', 'DRIVER_' + action.upper())
            ride.pop('pin', None)
            return ride


def pickup_coords(place):
    return {k: place[k] for k in ('latitude', 'longitude')}


def make_handler(service):
    from fleet35 import FleetError
    from experience34 import ExperienceError
    from staff38 import Staff, StaffError
    fleet = service.fleet
    staff = Staff(service.database)
    def authorize_admin(header, permission):
        # Compatibility only while no individual staff accounts exist. Once an owner
        # is bootstrapped, the shared development token stops working.
        with staff.connect() as db:
            has_staff = bool(db.execute('SELECT 1 FROM admin_staff LIMIT 1').fetchone())
        settings = getattr(service, 'settings', None)
        if not has_staff and not (settings and settings.environment == 'staging'):
            expected=os.environ.get('RIDENOVA_DEV_ADMIN_TOKEN','')
            if expected and secrets.compare_digest(header or '', 'Bearer '+expected):
                return {'id':'development-admin','username':'legacy-development','role':'OWNER'}
            fail(403,'FORBIDDEN','Development admin authorization required')
        return staff.authorize(header,permission)
    class Handler(BaseHTTPRequestHandler):
        server_version = 'RideNova/41.0'

        def log_message(self, *_):
            pass  # Do not print addresses, tokens, URLs or request bodies.

        def do_GET(self):
            self.dispatch()

        def do_POST(self):
            self.dispatch()

        def do_PATCH(self):
            self.dispatch()

        def dispatch(self):
            request_id = secrets.token_hex(8)
            try:
                self.connection.settimeout(15)
                path = self.path.split('?')[0].rstrip('/')
                settings = getattr(service, 'settings', None)
                staging = settings is not None and settings.environment == 'staging'
                if staging and (path.startswith('/v1/driver/') or
                    path in ('/v2/fleet/register', '/v2/fleet/auth/register', '/v2/fleet/auth/recover') or
                    path.startswith('/v1/admin/rides/') and path.endswith(('/transition', '/driver-position'))):
                    fail(403, 'DEVELOPMENT_ONLY', 'Unavailable in staging; contact the test administrator')
                body = {}
                if path == '/admin' and self.command == 'GET':
                    html = Path(__file__).with_name('admin').joinpath('index.html').read_bytes()
                    if staging:
                        html = html.replace(b'class="tag">Development</span>', b'class="tag">STAGING - invited tests only</span>')
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.send_header('Content-Length', str(len(html)))
                    self.end_headers()
                    self.wfile.write(html)
                    return
                if self.command in ('POST', 'PATCH'):
                    if self.headers.get('Transfer-Encoding'):
                        fail(400, 'INVALID_BODY', 'Chunked requests are not supported')
                    try:
                        length = int(self.headers.get('Content-Length', '0'))
                    except ValueError:
                        fail(400, 'INVALID_BODY', 'Invalid content length')
                    if path.startswith('/v2/fleet/driver/documents/'):
                        limit = 3 * 1024 * 1024
                    elif path == '/v1/passenger/quotes':
                        # A selected high-quality road polyline can legitimately exceed 32 KiB.
                        limit = 512 * 1024
                    else:
                        limit = 32768
                    if not 0 < length <= limit:
                        fail(413, 'BODY_TOO_LARGE', 'JSON body exceeds the endpoint size limit')
                    try:
                        body = json.loads(self.rfile.read(length))
                    except (ValueError, UnicodeError):
                        fail(400, 'INVALID_JSON', 'Invalid JSON body')
                    if not isinstance(body, dict):
                        fail(400, 'INVALID_JSON', 'Expected JSON object')
                if path == '/health' and self.command == 'GET':
                    result = {'status': 'ok', 'version': '41.0', 'build': 41, 'developmentOnly': True,
                              'authentication': 'development-otp'}
                elif path == '/v1/staff/login' and self.command == 'POST':
                    result = staff.login(body)
                elif path.startswith('/v1/staff/'):
                    parts = path.split('/')
                    if path == '/v1/staff/logout' and self.command == 'POST':
                        result = staff.logout(self.headers.get('Authorization'))
                    elif path == '/v1/staff/me' and self.command == 'GET':
                        result = {'staff': staff.authorize(self.headers.get('Authorization'), 'overview')}
                    elif path == '/v1/staff/accounts' and self.command == 'GET':
                        staff.authorize(self.headers.get('Authorization'), 'staff.read')
                        result = staff.list()
                    elif path == '/v1/staff/accounts' and self.command == 'POST':
                        actor = staff.authorize(self.headers.get('Authorization'), 'staff.write')
                        result = staff.create(actor,body)
                    elif len(parts)==6 and parts[3]=='accounts' and parts[5]=='status' and self.command=='POST':
                        actor=staff.authorize(self.headers.get('Authorization'),'staff.write')
                        result=staff.set_active(actor,parts[4],body.get('active'))
                    elif path == '/v1/staff/audit' and self.command == 'GET':
                        staff.authorize(self.headers.get('Authorization'), 'audit.read')
                        result=staff.audit()
                    else:
                        fail(404,'NOT_FOUND','Endpoint not found')
                elif path == '/v1/auth/request-otp' and self.command == 'POST':
                    result = service.request_otp(body)
                elif path == '/v1/auth/verify-otp' and self.command == 'POST':
                    legacy_session = self.headers.get('X-RideNova-Session', '')
                    legacy_owner = hashlib.sha256(legacy_session.encode()).hexdigest() if 20 <= len(legacy_session) <= 128 else None
                    result = service.verify_otp(body, legacy_owner)
                elif path == '/v1/auth/refresh' and self.command == 'POST':
                    result = service.refresh(body)
                elif path == '/v1/auth/logout' and self.command == 'POST':
                    result = service.logout(self.headers.get('Authorization'), body.get('refreshToken'))
                elif path == '/v2/fleet/auth/register' and self.command == 'POST':
                    result = fleet.register_account(body)
                elif path == '/v2/fleet/auth/login' and self.command == 'POST':
                    result = fleet.login(body)
                elif path == '/v2/fleet/auth/recover' and self.command == 'POST':
                    result = fleet.recover(body)
                elif path == '/v2/fleet/register' and self.command == 'POST':
                    result = fleet.register(body)
                elif path.startswith('/v2/fleet/admin/'):
                    tail=path[len('/v2/fleet/admin/'):]
                    permission=('fleet.read' if path.endswith('/drivers') or path.endswith('/audit') else
                                'documents.read' if path.endswith('/documents') or '/documents/' in path and not path.endswith('/review') else
                                'documents.write' if path.endswith('/review') else 'fleet.write')
                    actor = authorize_admin(self.headers.get('Authorization',''),permission)
                    if self.command == 'POST': staff.record(actor, 'FLEET_ACTION_ATTEMPT', path)

                    parts=path.split('/')
                    if path=='/v2/fleet/admin/drivers' and self.command=='GET':
                        from urllib.parse import parse_qs, urlsplit
                        params=parse_qs(urlsplit(self.path).query)
                        if params.get('paged',['0'])[0]=='1':
                            try:
                                page=int(params.get('page',['1'])[0]); limit=int(params.get('limit',['25'])[0])
                            except ValueError:
                                fail(400,'INVALID_PAGE','Invalid fleet page or limit')
                            if not 1 <= page <= 100000 or not 1 <= limit <= 100:
                                fail(400,'INVALID_PAGE','Fleet page or limit out of range')
                            status=params.get('status',[''])[0].strip()
                            if status not in ('','PENDING','APPROVED','SUSPENDED'):
                                fail(400,'INVALID_FILTER','Invalid fleet status')
                            search=params.get('q',[''])[0].strip()
                            if len(search)>80:
                                fail(400,'INVALID_FILTER','Fleet search limited to 80 characters')
                            where=[]; values=[]
                            if status:
                                where.append('status=?'); values.append(status)
                            if search:
                                where.append('(name LIKE ? OR vehicle LIKE ? OR plate LIKE ? OR id LIKE ?)')
                                values.extend(['%'+search+'%']*4)
                            clause=' WHERE '+' AND '.join(where) if where else ''
                            with service.connect() as db:
                                total=db.execute('SELECT COUNT(*) FROM fleet_drivers'+clause,tuple(values)).fetchone()[0]
                                ids=[r[0] for r in db.execute('SELECT id FROM fleet_drivers'+clause+' ORDER BY created_ms DESC,id DESC LIMIT ? OFFSET ?',tuple(values)+(limit,(page-1)*limit)).fetchall()]
                            # Preserve existing fleet.status enrichment without loading all drivers.
                            drivers=[dict(fleet.status(driver_id),id=driver_id) for driver_id in ids]
                            result={'developmentOnly':True,'drivers':drivers,'page':page,'limit':limit,
                                    'total':total,'pages':max(1,(total+limit-1)//limit)}
                        else:
                            result=fleet.list_drivers()
                    elif len(parts)>=7 and parts[4]=='drivers':
                        driver_id, action = parts[5], parts[6]
                        if len(parts)==7 and action=='status' and self.command=='POST': result=fleet.approve(driver_id,body)
                        elif len(parts)==7 and action=='eligibility' and self.command=='POST': result=fleet.set_eligibility(driver_id,body)
                        elif len(parts)==7 and action=='documents' and self.command=='GET': result=fleet.documents(driver_id)
                        elif len(parts)==7 and action=='audit' and self.command=='GET': result=fleet.audit(driver_id)
                        elif len(parts)==7 and action=='reset-token' and self.command=='POST': result=fleet.rotate_token(driver_id)
                        elif len(parts)==8 and action=='documents' and self.command=='GET': result=fleet.document_content(driver_id,parts[7])
                        elif len(parts)==9 and action=='documents' and parts[8]=='review' and self.command=='POST': result=fleet.review_document(driver_id,parts[7],body)
                        else: fail(404,'NOT_FOUND','Endpoint not found')
                    else:fail(404,'NOT_FOUND','Endpoint not found')
                elif path.startswith('/v2/fleet/driver/'):
                    with fleet.auth_lock:
                        driver_id=fleet.authenticate(self.headers.get('Authorization',''))
                        if staging:
                            with service.connect() as db:
                                invited = db.execute('SELECT phone FROM fleet_logins WHERE driver_id=?', (driver_id,)).fetchone()
                            if not invited or invited[0] not in settings.driver_phones:
                                fail(403, 'STAGING_INVITE_REQUIRED', 'Staging invitation is no longer active')
                        tail=path[len('/v2/fleet/driver/'):]
                        if tail=='logout' and self.command=='POST':result=fleet.logout(driver_id)
                        elif tail=='login-details' and self.command=='GET':result=fleet.login_details(driver_id)
                        elif tail=='login-details' and self.command=='POST':result=fleet.set_login(driver_id,body)
                        elif tail=='password' and self.command=='POST':result=fleet.change_password(driver_id,body)
                        elif tail=='account-overview' and self.command=='GET':result=fleet.account_overview(driver_id)
                        elif tail=='support-cases' and self.command=='GET':result=service.experience.list_cases('DRIVER',driver_id)
                        elif tail=='support-cases' and self.command=='POST':result=service.experience.create_case('DRIVER',driver_id,body)
                        elif tail.startswith('rides/') and len(tail.split('/'))==3 and tail.endswith('/experience') and self.command=='GET':
                            result=service.experience.ride_experience('DRIVER',driver_id,tail.split('/')[1])
                        elif tail.startswith('rides/') and len(tail.split('/'))==3 and tail.endswith('/rating') and self.command=='POST':
                            result=service.experience.rate('DRIVER',driver_id,tail.split('/')[1],body)
                        elif tail=='status' and self.command=='GET':result=fleet.status(driver_id)
                        elif tail=='profile' and self.command=='POST':result=fleet.update_profile(driver_id,body)
                        elif tail=='presence' and self.command=='POST':result=fleet.presence(driver_id,body)
                        elif tail=='availability' and self.command=='POST':result=fleet.availability(driver_id,body)
                        elif tail=='location' and self.command=='POST':result=fleet.location(driver_id,body)
                        elif tail in ('offer','requests/current') and self.command=='GET':result=fleet.offer(driver_id)
                        elif tail=='documents' and self.command=='GET':result=fleet.documents(driver_id)
                        elif tail.startswith('documents/') and len(tail.split('/'))==2 and self.command=='POST':result=fleet.submit_document(driver_id,tail.split('/')[1],body)
                        elif tail=='rides/active' and self.command=='GET':result=fleet.active_ride(driver_id)
                        elif tail=='trips' and self.command=='GET':result=fleet.history(driver_id)
                        elif tail=='rides/accept' and self.command=='POST':result=fleet.accept(driver_id,body.get('rideId',''))
                        elif tail.startswith('rides/') and len(tail.split('/'))==3 and self.command=='POST':
                            result=fleet.action(driver_id,tail.split('/')[1],tail.split('/')[2],body)
                        else:fail(404,'NOT_FOUND','Endpoint not found')
                elif path.startswith('/v1/admin/'):
                    permission=('overview' if path.endswith('/overview') else
                                'support.write' if path.endswith('/status') and 'support-cases' in path else
                                'support.read' if 'support-cases' in path or path.endswith('/feedback') else
                                'ride.read' if path.endswith('/rides') else
                                'ride.write' if path.endswith('/transition') or path.endswith('/driver-position') else
                                'ride.read' if '/rides/' in path else 'overview')
                    actor=authorize_admin(self.headers.get('Authorization',''),permission)
                    if self.command=='POST': staff.record(actor,'ADMIN_ACTION_ATTEMPT',path)

                    parts = path.split('/')
                    if path == '/v1/admin/overview' and self.command == 'GET':
                        result = service.admin_overview()
                        from staff38 import PERMS
                        permissions=PERMS[actor['role']]
                        if 'finance.read' not in permissions:
                            result.pop('ledger',None)
                            result.pop('totals',None)
                        if 'fleet.read' not in permissions:
                            result.pop('fleetDrivers',None)
                            result.pop('driver',None)
                        if 'ride.read' not in permissions:
                            result.pop('rides',None)
                    elif path == '/v1/admin/rides' and self.command == 'GET':
                        from urllib.parse import urlsplit,parse_qs
                        params=parse_qs(urlsplit(self.path).query)
                        try:
                            page=int(params.get('page',['1'])[0]); limit=int(params.get('limit',['25'])[0])
                        except ValueError:
                            fail(400,'INVALID_PAGE','Invalid page or limit')
                        if page < 1 or page > 100000 or limit < 1 or limit > 100:
                            fail(400,'INVALID_PAGE','Page out of bounds (limit 1-100)')
                        statuses={'SEARCHING','DRIVER_ASSIGNED','DRIVER_ARRIVED','TRIP_STARTED','COMPLETED','CANCELLED_BY_RIDER','CANCELLED_BY_DRIVER','SCHEDULED'}
                        query=params.get('q',[''])[0].strip()
                        if len(query)>64 or not re.fullmatch(r'[A-Za-z0-9_-]*',query):
                            fail(400,'INVALID_FILTER','Search using a ride ID only (maximum 64 characters)')
                        status_filter=params.get('status',[''])[0]
                        if status_filter and status_filter not in statuses:
                            fail(400,'INVALID_FILTER','Unsupported status')
                        conditions=[]
                        parameters=[]
                        if status_filter:
                            conditions.append("json_extract(payload,'$.status')=?")
                            parameters.append(status_filter)
                        if query:
                            conditions.append('instr(id,?)>0')
                            parameters.append(query)
                        where='WHERE '+' AND '.join(conditions) if conditions else ''
                        values=tuple(parameters)
                        with service.connect() as db:
                            total=db.execute('SELECT COUNT(*) FROM rides '+where,values).fetchone()[0]
                            rows=db.execute('SELECT payload FROM rides '+where+
                                " ORDER BY CAST(json_extract(payload,'$.updatedAtEpochMs') AS INTEGER) DESC, id DESC LIMIT ? OFFSET ?",
                                values+(limit,(page-1)*limit)).fetchall()
                        result={'page':page,'limit':limit,'total':total,'pages':max(1,(total+limit-1)//limit),
                                'rides':[{'id':r['id'],'status':r.get('status'),
                                  'category':r.get('option',{}).get('title',''),
                                  'driverId':r.get('fleetDriverId'),'driverName':(r.get('driver') or {}).get('name'),
                                  'pickup':service.fleet.label(r.get('draft',{}).get('pickup',{})),
                                  'destination':service.fleet.label(r.get('draft',{}).get('destination',{})),
                                  'updatedAtEpochMs':r.get('updatedAtEpochMs',0),
                                  'fareCents':r.get('option',{}).get('breakdown',{}).get('totalCents',0)}
                                  for (payload,) in rows for r in [json.loads(payload)]]}
                    elif path == '/v1/admin/support-cases' and self.command == 'GET':
                        from urllib.parse import parse_qs,urlsplit
                        params=parse_qs(urlsplit(self.path).query)
                        if params.get('paged',['0'])[0]=='1':
                            try:
                                page=int(params.get('page',['1'])[0]);limit=int(params.get('limit',['25'])[0])
                            except ValueError:
                                fail(400,'INVALID_PAGE','Invalid support page or limit')
                            if not 1<=page<=100000 or not 1<=limit<=100:
                                fail(400,'INVALID_PAGE','Support page or limit out of range')
                            status=params.get('status',[''])[0].strip()
                            if status not in ('','OPEN','IN_REVIEW','RESOLVED'):
                                fail(400,'INVALID_FILTER','Invalid support status')
                            search=params.get('q',[''])[0].strip()
                            if len(search)>80:
                                fail(400,'INVALID_FILTER','Support search limited to 80 characters')
                            clauses=[];values=[]
                            if status:
                                clauses.append('status=?');values.append(status)
                            if search:
                                clauses.append('(id LIKE ? OR ride_id LIKE ? OR description LIKE ?)')
                                values.extend(['%'+search+'%']*3)
                            clause=' WHERE '+' AND '.join(clauses) if clauses else ''
                            with service.connect() as db:
                                total=db.execute('SELECT COUNT(*) FROM support_cases'+clause,tuple(values)).fetchone()[0]
                                rows=db.execute('SELECT id,ride_id,reporter_role,category,description,status,admin_note,created_ms,updated_ms,reporter_id FROM support_cases'+clause+' ORDER BY updated_ms DESC,id DESC LIMIT ? OFFSET ?',tuple(values)+(limit,(page-1)*limit)).fetchall()
                            result={'cases':[service.experience._case_json(row,True) for row in rows],
                                    'page':page,'limit':limit,'total':total,'pages':max(1,(total+limit-1)//limit)}
                        else:
                            result=service.experience.admin_cases()
                    elif path == '/v1/admin/feedback' and self.command == 'GET':
                        result = service.experience.admin_feedback()
                    elif len(parts) == 6 and parts[3] == 'support-cases' and parts[5] == 'status' and self.command == 'POST':
                        result = service.experience.update_case(parts[4], body)
                    elif len(parts) == 6 and parts[3] == 'rides' and parts[5] == 'transition' and self.command == 'POST':
                        result = service.transition(parts[4], body.get('status'))
                    elif len(parts) == 6 and parts[3] == 'rides' and parts[5] == 'driver-position' and self.command == 'POST':
                        result = service.report_driver_position(parts[4], body)
                    elif len(parts) == 6 and parts[3] == 'rides' and parts[5] == 'events' and self.command == 'GET':
                        with service.connect() as db:
                            result = {'events': [dict(zip(('sequence', 'atEpochMs', 'type', 'data'), (r[0], r[1], r[2], json.loads(r[3]))))
                                for r in db.execute('SELECT sequence,at_ms,type,payload FROM events WHERE ride_id=? ORDER BY sequence', (parts[4],))]}
                    else:
                        fail(404, 'NOT_FOUND', 'Endpoint not found')
                elif path.startswith('/v1/driver/'):
                    expected = os.environ.get('RIDENOVA_DEV_DRIVER_TOKEN', '')
                    admin = os.environ.get('RIDENOVA_DEV_ADMIN_TOKEN', '')
                    if not expected or expected == admin or not secrets.compare_digest(
                            self.headers.get('Authorization', ''), 'Bearer ' + expected):
                        fail(403, 'FORBIDDEN', 'Development driver authorization required')
                    if path == '/v1/driver/status' and self.command == 'GET':
                        result = service.driver_status()
                    elif path == '/v1/driver/availability' and self.command == 'POST':
                        result = service.driver_availability(body)
                    elif path == '/v1/driver/location' and self.command == 'POST':
                        result = service.driver_presence(body)
                    elif path == '/v1/driver/requests/current' and self.command == 'GET':
                        result = service.driver_offer()
                    elif path == '/v1/driver/rides/active' and self.command == 'GET':
                        result = service.driver_ride()
                    elif path == '/v1/driver/trips' and self.command == 'GET':
                        result = service.driver_history()
                    elif path.startswith('/v1/driver/rides/') and self.command == 'POST':
                        parts = path.split('/')
                        if len(parts) == 6:
                            result = service.driver_action(parts[4], parts[5], body)
                        else:
                            fail(404, 'NOT_FOUND', 'Endpoint not found')
                    else:
                        fail(404, 'NOT_FOUND', 'Endpoint not found')
                else:
                    owner = service.authenticate(self.headers.get('Authorization'))
                    if path == '/v1/passenger/me' and self.command in ('GET', 'PATCH'):
                        result = service.profile(owner, body if self.command == 'PATCH' else None)
                    elif path == '/v1/passenger/account-data' and self.command == 'GET':
                        result = service.account_places(owner)
                    elif path == '/v1/passenger/saved-places' and self.command == 'POST':
                        result = service.change_saved_place(owner, body)
                    elif path == '/v1/passenger/recent-destinations' and self.command == 'POST':
                        result = service.change_recent_destination(owner, body)
                    elif path == '/v1/passenger/payment-methods':
                        result = service.add_payment_method(owner, body) if self.command == 'POST' else service.payment_methods(owner)
                    elif path.startswith('/v1/passenger/payment-methods/') and self.command == 'POST':
                        parts = path.split('/')
                        if len(parts) == 6 and parts[5] in ('default', 'remove'):
                            result = service.update_payment_method(owner, parts[4], parts[5])
                        else:
                            fail(404, 'NOT_FOUND', 'Endpoint not found')
                    elif path == '/v1/passenger/availability' and self.command == 'POST':
                        result = service.passenger_availability(body)
                    elif path == '/v1/passenger/quotes' and self.command == 'POST':
                        result = service.quote(owner, body)
                    elif path == '/v1/passenger/rides':
                        result = service.create(owner, body) if self.command == 'POST' else service.list(owner)
                    elif path == '/v1/passenger/support-cases':
                        result = service.experience.create_case('PASSENGER', owner, body) if self.command == 'POST' else service.experience.list_cases('PASSENGER', owner)
                    elif path.startswith('/v1/passenger/rides/'):
                        parts = path.split('/')
                        if len(parts) == 5 and self.command == 'GET':
                            result = service.get(owner, parts[4])
                        elif len(parts) == 6 and parts[5] == 'cancel' and self.command == 'POST':
                            result = service.cancel(owner, parts[4])
                        elif len(parts) == 6 and parts[5] == 'experience' and self.command == 'GET':
                            result = service.experience.ride_experience('PASSENGER', owner, parts[4])
                        elif len(parts) == 6 and parts[5] == 'rating' and self.command == 'POST':
                            result = service.experience.rate('PASSENGER', owner, parts[4], body)
                        else:
                            fail(404, 'NOT_FOUND', 'Endpoint not found')
                    else:
                        fail(404, 'NOT_FOUND', 'Endpoint not found')
                if self.command == 'POST' and (path.startswith('/v1/admin/') or path.startswith('/v2/fleet/admin/')):
                    staff.record(actor,'ADMIN_ACTION_SUCCEEDED',path)
                status = 200
            except StaffError as exc:
                status, result = exc.status, {'code': exc.code, 'message': exc.message}
            except FleetError as exc:
                status, result = exc.status, {'code': exc.code, 'message': exc.message}
            except ExperienceError as exc:
                status, result = exc.status, {'code': exc.code, 'message': exc.message}
            except APIError as exc:
                status, result = exc.status, {'code': exc.code, 'message': exc.message}
            except Exception:
                status, result = 500, {'code': 'INTERNAL_ERROR', 'message': 'Request failed; retry safely with the same quote token'}
            data = json.dumps(result, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Request-ID', request_id)
            self.end_headers()
            self.wfile.write(data)
    return Handler


if __name__ == '__main__':
    if os.environ.get('RIDENOVA_ENVIRONMENT', 'development') != 'development':
        raise SystemExit('This server is development-only. Production hosting is intentionally disabled.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1',
                        help='Bind address. Use 0.0.0.0 only on a trusted development network.')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--database', default='ridenova-dev.sqlite3')
    args = parser.parse_args()
    service = Service(args.database)
    stop = threading.Event()
    def scheduler():
        while not stop.is_set():
            try:
                service.activate_due()
            except Exception:
                print('Development scheduler tick failed; it will retry. Inspect the database/server configuration.')
            stop.wait(5)
    worker = threading.Thread(target=scheduler, daemon=True)
    worker.start()
    print(f'RideNova Build 41 / Admin v0.8.0 DEVELOPMENT ONLY on http://{args.host}:{args.port}; Trip Radar enabled; no real charges')
    server = ThreadingHTTPServer((args.host, args.port), make_handler(service))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        worker.join(timeout=10)
