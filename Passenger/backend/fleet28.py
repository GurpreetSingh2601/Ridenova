"""Build 28 development multi-driver foundation. No real identity verification or payouts."""
import hashlib
import hmac
import json
import math
import re
import secrets
import sqlite3

class FleetError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message

def reject(status, code, message):
    raise FleetError(status, code, message)

class Fleet:
    def __init__(self, service):
        self.service = service
        if service.postgres:
            return
        with service.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS fleet_drivers (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, vehicle TEXT NOT NULL,
                plate TEXT NOT NULL, category TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING', online INTEGER NOT NULL DEFAULT 0,
                lat REAL, lng REAL, located_ms INTEGER, created_ms INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS fleet_credentials (
                token_hash TEXT PRIMARY KEY, driver_id TEXT NOT NULL UNIQUE,
                FOREIGN KEY(driver_id) REFERENCES fleet_drivers(id));
            CREATE TABLE IF NOT EXISTS fleet_offers (
                driver_id TEXT PRIMARY KEY, ride_id TEXT NOT NULL UNIQUE,
                expires_ms INTEGER NOT NULL, FOREIGN KEY(driver_id) REFERENCES fleet_drivers(id));
            CREATE TABLE IF NOT EXISTS fleet_declines (
                driver_id TEXT NOT NULL, ride_id TEXT NOT NULL, until_ms INTEGER NOT NULL,
                PRIMARY KEY(driver_id,ride_id));
            CREATE TABLE IF NOT EXISTS fleet_documents (
                driver_id TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'NOT_SUBMITTED',
                expiry_date TEXT, PRIMARY KEY(driver_id,kind));
            CREATE TABLE IF NOT EXISTS fleet_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, driver_id TEXT NOT NULL, actor TEXT NOT NULL,
                action TEXT NOT NULL, at_ms INTEGER NOT NULL);
            """)

    def register(self, body):
        def field(k, n):
            v=body.get(k)
            if not isinstance(v,str) or not 1<=len(v.strip())<=n:
                reject(400,'INVALID_PROFILE',f'Invalid {k}')
            return v.strip()
        name,vehicle,plate=field('name',80),field('vehicle',100),field('plate',20)
        category=body.get('category')
        if category not in self.service.config['tiers']:
            reject(400,'INVALID_CATEGORY','Unknown category')
        driver_id='drv_'+secrets.token_hex(12)
        token=secrets.token_urlsafe(40)
        with self.service.connect() as db:
            db.execute('INSERT INTO fleet_drivers(id,name,vehicle,plate,category,created_ms) VALUES (?,?,?,?,?,?)',
                       (driver_id,name,vehicle,plate,category,self.service.clock()))
            db.execute('INSERT INTO fleet_credentials VALUES (?,?)',(hashlib.sha256(token.encode()).hexdigest(),driver_id))
            for kind in ('LICENCE','INSURANCE','REGISTRATION','INSPECTION'):
                db.execute('INSERT INTO fleet_documents(driver_id,kind) VALUES (?,?)',(driver_id,kind))
            self._audit(db,driver_id,'driver','REGISTERED')
        return {'driverId':driver_id,'developmentToken':token,'status':'PENDING','developmentOnly':True,
                'notice':'Test credential only; no phone, identity or document verification performed.'}

    def authenticate(self, header):
        if not header.startswith('Bearer ') or len(header)>256:
            reject(401,'FLEET_AUTH_REQUIRED','Individual development driver token required')
        digest=hashlib.sha256(header[7:].encode()).hexdigest()
        with self.service.connect() as db:
            row=db.execute('SELECT driver_id FROM fleet_credentials WHERE token_hash=?',(digest,)).fetchone()
        if not row: reject(401,'FLEET_AUTH_REQUIRED','Invalid individual development driver token')
        return row[0]

    def _audit(self,db,driver,actor,action):
        db.execute('INSERT INTO fleet_audit(driver_id,actor,action,at_ms) VALUES (?,?,?,?)',
                   (driver,actor,action,self.service.clock()))

    def list_drivers(self):
        with self.service.connect() as db:
            rows=db.execute('SELECT id,name,vehicle,plate,category,status,online,located_ms FROM fleet_drivers ORDER BY created_ms').fetchall()
        return {'developmentOnly':True,'drivers':[dict(zip(('id','name','vehicle','plate','category','status','online','lastLocationEpochMs'),
                    (r[0],r[1],r[2],r[3],r[4],r[5],bool(r[6]),r[7]))) for r in rows]}

    def approve(self,driver_id,body):
        status=body.get('status')
        if status not in ('APPROVED','SUSPENDED','PENDING'):
            reject(400,'INVALID_STATUS','Use APPROVED, SUSPENDED or PENDING')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT status FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone()
            if not row: reject(404,'DRIVER_NOT_FOUND','Unknown driver')
            db.execute('UPDATE fleet_drivers SET status=?,online=CASE WHEN ?="APPROVED" THEN online ELSE 0 END WHERE id=?',
                       (status,status,driver_id))
            if status!='APPROVED': db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
            self._audit(db,driver_id,'development-admin','STATUS_'+status)
        return {'driverId':driver_id,'status':status,'developmentOnly':True,'notice':'Manual development approval, not regulatory verification'}

    def documents(self,driver_id):
        with self.service.connect() as db:
            rows=db.execute('SELECT kind,status,expiry_date FROM fleet_documents WHERE driver_id=? ORDER BY kind',(driver_id,)).fetchall()
        return {'documents':[{'kind':a,'status':b,'expiryDate':c} for a,b,c in rows],
                'uploadSupported':False,'verified':False,'developmentOnly':True}

    def presence(self,driver_id,body):
        online=body.get('online')
        if type(online) is not bool: reject(400,'INVALID_AVAILABILITY','online must be boolean')
        lat,lng=body.get('latitude'),body.get('longitude')
        if online and (type(lat) not in (int,float) or type(lng) not in (int,float) or
                       not math.isfinite(lat) or not math.isfinite(lng) or not -90<=lat<=90 or not -180<=lng<=180):
            reject(400,'INVALID_POSITION','Online requires valid coordinates')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT status FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone()
            if not row: reject(404,'DRIVER_NOT_FOUND','Unknown driver')
            if online and row[0]!='APPROVED': reject(403,'DRIVER_NOT_APPROVED','Admin approval required')
            if online:
                db.execute('UPDATE fleet_drivers SET online=1,lat=?,lng=?,located_ms=? WHERE id=?',(lat,lng,self.service.clock(),driver_id))
            else:
                db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?',(driver_id,))
                db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
        return {'online':online,'driverId':driver_id}

    def offer(self,driver_id):
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            driver=db.execute('SELECT category,status,online,lat,lng,located_ms FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone()
            if not driver or driver[1]!='APPROVED' or not driver[2] or driver[5] is None or self.service.clock()-driver[5]>30000:
                db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
                return {}
            now=self.service.clock()
            existing=db.execute('SELECT ride_id,expires_ms FROM fleet_offers WHERE driver_id=?',(driver_id,)).fetchone()
            if existing and existing[1]<=now:
                db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
                db.execute('INSERT OR REPLACE INTO fleet_declines VALUES (?,?,?)',(driver_id,existing[0],now+20000))
                existing=None
            if existing:
                row=db.execute('SELECT payload FROM rides WHERE id=?',(existing[0],)).fetchone()
                if row and json.loads(row[0])['status']=='SEARCHING':
                    return {'rideId':existing[0],'expiresAtEpochMs':existing[1]}
                db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
            # Reserve the ride for one driver atomically. Existing legacy driver offers excluded.
            legacy={r[0] for r in db.execute('SELECT ride_id FROM driver_offer_state')}
            reserved={r[0] for r in db.execute('SELECT ride_id FROM fleet_offers')}
            declined={r[0] for r in db.execute('SELECT ride_id FROM fleet_declines WHERE driver_id=? AND until_ms>?',(driver_id,now))}
            choices=[]
            for (payload,) in db.execute('SELECT payload FROM rides'):
                ride=json.loads(payload)
                if ride['status']!='SEARCHING' or ride['id'] in legacy|reserved|declined or ride['option']['tier']!=driver[0]: continue
                p=ride['draft']['pickup']
                distance=self.service.distance_km(driver[3],driver[4],p['latitude'],p['longitude'])
                choices.append((distance,ride['requestedAtEpochMs'],ride))
            if not choices:return {}
            distance,_,ride=min(choices,key=lambda item:(item[0],item[1]))
            expires=now+20000
            db.execute('INSERT INTO fleet_offers VALUES (?,?,?)',(driver_id,ride['id'],expires))
            return {'rideId':ride['id'],'expiresAtEpochMs':expires,'pickupDistanceKm':round(distance,2),
                    'tripDistanceKm':ride['draft']['routeEstimate']['distanceKm'],
                    'tripEtaMin':ride['draft']['routeEstimate']['durationMinutes'],
                    'estimatedGrossBeforeCostsCad':ride['option']['breakdown']['driverGrossBeforeCostsCents']/100}

    def accept(self,driver_id,ride_id):
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now=self.service.clock()
            row=db.execute('SELECT expires_ms FROM fleet_offers WHERE driver_id=? AND ride_id=?',(driver_id,ride_id)).fetchone()
            if not row or row[0]<=now: reject(409,'OFFER_EXPIRED','No valid offer for this driver')
            driver=db.execute('SELECT name,vehicle,plate,status,online FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone()
            if not driver or driver[3]!='APPROVED' or not driver[4]:reject(403,'DRIVER_UNAVAILABLE','Driver not eligible')
            record=db.execute('SELECT payload FROM rides WHERE id=?',(ride_id,)).fetchone()
            if not record:reject(404,'RIDE_NOT_FOUND','Ride not found')
            ride=json.loads(record[0])
            if ride['status']!='SEARCHING': reject(409,'RIDE_UNAVAILABLE','Already assigned')
            for (payload,) in db.execute('SELECT payload FROM rides'):
                other=json.loads(payload)
                if other.get('fleetDriverId')==driver_id and other['status'] in ('DRIVER_ASSIGNED','DRIVER_ARRIVED','TRIP_STARTED'):
                    reject(409,'DRIVER_BUSY','Active trip exists')
            ride.update(status='DRIVER_ASSIGNED',updatedAtEpochMs=now,fleetDriverId=driver_id,
                        driver={'name':driver[0],'vehicle':driver[1],'plate':driver[2],'pickupEtaMinutes':None},
                        pin=str(secrets.randbelow(9000)+1000))
            db.execute('UPDATE rides SET payload=? WHERE id=?',(json.dumps(ride),ride_id))
            db.execute('DELETE FROM fleet_offers WHERE ride_id=?',(ride_id,))
            self._audit(db,driver_id,'driver','ACCEPTED')
            return {'rideId':ride_id,'status':'DRIVER_ASSIGNED','driverId':driver_id}
