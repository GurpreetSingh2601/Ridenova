"""Build 29 shared development fleet. All claims/changes are SQLite transactions.
Document review is a test workflow, not identity or regulatory verification.
"""
import base64
import binascii
import hashlib
import json
import math
import secrets
from datetime import datetime, timezone, date
from fleet28 import Fleet as Foundation, FleetError, reject

ACTIVE = ('DRIVER_ASSIGNED', 'DRIVER_ARRIVED', 'TRIP_STARTED')
KINDS = ('LICENCE', 'INSURANCE', 'REGISTRATION', 'INSPECTION')
MAX_DOCUMENT = 2 * 1024 * 1024

class Fleet(Foundation):
    def __init__(self, service):
        super().__init__(service)
        if service.postgres:
            return
        with service.connect() as db:
            columns = {r[1] for r in db.execute('PRAGMA table_info(fleet_documents)')}
            for name, kind in [('filename','TEXT'), ('mime','TEXT'), ('content','BLOB'),
                               ('revision','INTEGER NOT NULL DEFAULT 0'), ('note','TEXT'), ('submitted_ms','INTEGER')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE fleet_documents ADD COLUMN {name} {kind}')
            db.execute('CREATE TABLE IF NOT EXISTS fleet_pin_attempts (ride_id TEXT PRIMARY KEY, attempts INTEGER NOT NULL, until_ms INTEGER NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS fleet_audit_driver ON fleet_audit(driver_id, id)')
            # Build 28 API-assigned rides omitted fields required by Passenger Android.
            for ride in self.rides(db):
                if ride.get('fleetDriverId') and ride.get('driver'):
                    profile=ride['driver']
                    profile.setdefault('rating',5.0)
                    profile.setdefault('colour','')
                    if profile.get('pickupEtaMinutes') is None: profile['pickupEtaMinutes']=5
                    db.execute('UPDATE rides SET payload=? WHERE id=?',(json.dumps(ride),ride['id']))

    def today(self):
        return datetime.fromtimestamp(self.service.clock()/1000, timezone.utc).date().isoformat()

    def ready(self, db, driver_id):
        rows = db.execute('SELECT kind,status,expiry_date FROM fleet_documents WHERE driver_id=?', (driver_id,)).fetchall()
        return len(rows)==len(KINDS) and all(s=='APPROVED' and e and e>=self.today() for _,s,e in rows)

    def active(self, db, driver_id):
        return next((r for r in self.rides(db) if r.get('fleetDriverId')==driver_id and r['status'] in ACTIVE), None)

    def rides(self, db):
        return [json.loads(r[0]) for r in db.execute('SELECT payload FROM rides')]

    def eligible(self, db, row):
        # id,name,vehicle,plate,category,status,online,lat,lng,located_ms,created_ms
        return (row[5]=='APPROVED' and row[6] and row[9] is not None and
                0 <= self.service.clock()-row[9] <= 30000 and self.ready(db,row[0]) and not self.active(db,row[0]))

    def status(self, driver_id):
        with self.service.connect() as db:
            row=db.execute('SELECT * FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone()
            if not row: reject(404,'DRIVER_NOT_FOUND','Unknown driver')
            active=self.active(db,driver_id)
            ready=self.ready(db,driver_id)
            online=bool(row[6] and row[5]=='APPROVED' and ready)
            result={'driverId':row[0],'name':row[1],'vehicle':row[2],'plate':row[3], 'category':row[4],
                    'status':row[5],'online':online,'documentsReady':ready,
                    'activeRideId':active['id'] if active else None,'activeRideStatus':active['status'] if active else None}
            fresh=row[9] is not None and 0 <= self.service.clock()-row[9] <= 30000
            reason = ('ACTIVE_TRIP' if active else 'APPROVAL_REQUIRED' if row[5]!='APPROVED'
                      else 'DOCUMENTS_REQUIRED' if not ready else 'OFFLINE' if not row[6]
                      else 'LOCATION_REQUIRED' if row[9] is None else 'LOCATION_STALE' if not fresh else 'READY')
            result.update(dispatchReady=reason=='READY', dispatchReason=reason,
                          serverTimeEpochMs=self.service.clock())
            if row[9] is not None:
                result['lastLocation']={'latitude':row[7],'longitude':row[8],'recordedAtEpochMs':row[9],
                                        'ageSeconds':max(0,(self.service.clock()-row[9])//1000)}
            return result

    def list_drivers(self):
        result=super().list_drivers()
        for driver in result['drivers']:
            driver.update(self.status(driver['id']))
        return result

    def approve(self, driver_id, body):
        status=body.get('status')
        if status not in ('APPROVED','PENDING','SUSPENDED'): reject(400,'INVALID_STATUS','Unknown status')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone():
                reject(404,'DRIVER_NOT_FOUND','Unknown driver')
            if status=='APPROVED' and not self.ready(db,driver_id):
                reject(409,'DOCUMENTS_REQUIRED','Approve all four current documents first')
            db.execute('UPDATE fleet_drivers SET status=?, online=CASE WHEN ?="APPROVED" THEN online ELSE 0 END WHERE id=?',(status,status,driver_id))
            db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
            self._audit(db,driver_id,'development-admin','STATUS_'+status)
        return self.status(driver_id)

    def update_profile(self, driver_id, body):
        values=[]
        for key,limit in (('name',80),('vehicle',100),('plate',20)):
            value=body.get(key)
            if not isinstance(value,str) or not 1<=len(value.strip())<=limit: reject(400,'INVALID_PROFILE','Invalid '+key)
            values.append(value.strip())
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.active(db,driver_id): reject(409,'ACTIVE_RIDE','Finish the active trip before changing your profile')
            old=db.execute('SELECT name,vehicle,plate FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone()
            if not old: reject(404,'DRIVER_NOT_FOUND','Unknown driver')
            if tuple(values)!=tuple(old):
                db.execute('UPDATE fleet_drivers SET name=?,vehicle=?,plate=?,online=0,status=CASE WHEN status="SUSPENDED" THEN status ELSE "PENDING" END WHERE id=?',(*values,driver_id))
                db.execute('UPDATE fleet_documents SET status="PENDING",revision=revision+1,note="Profile changed; review again" WHERE driver_id=? AND content IS NOT NULL',(driver_id,))
                db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
                self._audit(db,driver_id,'driver','PROFILE_CHANGED')
        return self.status(driver_id)

    def documents(self, driver_id):
        with self.service.connect() as db:
            rows=db.execute('SELECT kind,status,expiry_date,filename,mime,revision,note,submitted_ms FROM fleet_documents WHERE driver_id=? ORDER BY kind',(driver_id,)).fetchall()
        return {'documents':[dict(zip(('kind','status','expiryDate','filename','mime','revision','note','submittedAtEpochMs'),r),
                    expired=bool(r[2] and r[2]<self.today())) for r in rows],
                'uploadSupported':True,'maxBytes':MAX_DOCUMENT,'developmentOnly':True,'verified':False}

    def submit_document(self, driver_id, kind, body):
        if kind not in KINDS: reject(400,'INVALID_KIND','Unknown document kind')
        filename=body.get('filename')
        if not isinstance(filename,str) or not 1<=len(filename)<=120 or '/' in filename or '\\' in filename:
            reject(400,'INVALID_FILENAME','Use a filename of at most 120 characters')
        expiry=body.get('expiryDate')
        try:
            if not isinstance(expiry,str) or date.fromisoformat(expiry).isoformat()!=expiry or expiry<self.today(): raise ValueError()
        except (ValueError,TypeError): reject(400,'INVALID_EXPIRY','Use a current or future expiry date YYYY-MM-DD')
        try:
            encoded=body.get('contentBase64')
            if not isinstance(encoded,str) or len(encoded)>MAX_DOCUMENT*4//3+8: raise ValueError()
            data=base64.b64decode(encoded,validate=True)
        except (ValueError,binascii.Error): reject(400,'INVALID_DOCUMENT','Invalid base64 document')
        mime=body.get('mime')
        valid=(mime=='application/pdf' and data.startswith(b'%PDF-')) or (mime=='image/png' and data.startswith(b'\x89PNG\r\n\x1a\n')) or (mime=='image/jpeg' and data.startswith(b'\xff\xd8\xff'))
        if not 1<=len(data)<=MAX_DOCUMENT or not valid: reject(400,'INVALID_DOCUMENT','Use PDF, PNG or JPEG, up to 2 MiB')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.active(db,driver_id): reject(409,'ACTIVE_RIDE','Finish your active ride before replacing documents')
            row=db.execute('SELECT revision FROM fleet_documents WHERE driver_id=? AND kind=?',(driver_id,kind)).fetchone()
            if not row: reject(404,'DRIVER_NOT_FOUND','Unknown driver')
            if type(body.get('revision')) is not int or body['revision']!=row[0]: reject(409,'DOCUMENT_CHANGED','Refresh the checklist before uploading')
            db.execute('UPDATE fleet_documents SET status="PENDING",expiry_date=?,filename=?,mime=?,content=?,revision=revision+1,note=NULL,submitted_ms=? WHERE driver_id=? AND kind=?',
                       (expiry,filename,mime,data,self.service.clock(),driver_id,kind))
            db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?',(driver_id,))
            db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
            self._audit(db,driver_id,'driver','DOCUMENT_SUBMITTED_'+kind)
        return self.documents(driver_id)

    def review_document(self, driver_id, kind, body):
        status,note=body.get('status'),body.get('note','')
        if status not in ('APPROVED','REJECTED') or not isinstance(note,str) or len(note)>500 or (status=='REJECTED' and not note.strip()):
            reject(400,'INVALID_REVIEW','Approve or reject; rejection needs a note (up to 500 characters)')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT revision,content,expiry_date FROM fleet_documents WHERE driver_id=? AND kind=?',(driver_id,kind)).fetchone()
            if not row or not row[1]: reject(404,'DOCUMENT_NOT_FOUND','No uploaded document')
            if type(body.get('revision')) is not int or row[0]!=body['revision']: reject(409,'DOCUMENT_CHANGED','Document changed; reload before reviewing')
            if status=='APPROVED' and row[2]<self.today(): reject(409,'DOCUMENT_EXPIRED','Cannot approve an expired document')
            db.execute('UPDATE fleet_documents SET status=?,note=?,revision=revision+1 WHERE driver_id=? AND kind=?',(status,note.strip(),driver_id,kind))
            if status=='REJECTED':
                db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?',(driver_id,))
                db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
            self._audit(db,driver_id,'development-admin','DOCUMENT_'+status+'_'+kind)
        return self.documents(driver_id)

    def document_content(self, driver_id, kind):
        with self.service.connect() as db:
            row=db.execute('SELECT filename,mime,content,revision FROM fleet_documents WHERE driver_id=? AND kind=?',(driver_id,kind)).fetchone()
        if not row or not row[2]: reject(404,'DOCUMENT_NOT_FOUND','No uploaded document')
        return {'filename':row[0],'mime':row[1],'contentBase64':base64.b64encode(row[2]).decode(),'revision':row[3]}

    def audit(self, driver_id):
        with self.service.connect() as db:
            rows=db.execute('SELECT id,actor,action,at_ms FROM fleet_audit WHERE driver_id=? ORDER BY id DESC LIMIT 200',(driver_id,)).fetchall()
        return {'events':[dict(zip(('id','actor','action','atEpochMs'),r)) for r in rows]}

    def rotate_token(self, driver_id):
        token=secrets.token_urlsafe(40)
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.active(db,driver_id): reject(409,'ACTIVE_RIDE','Finish the ride before resetting access')
            changed=db.execute('UPDATE fleet_credentials SET token_hash=? WHERE driver_id=?',(hashlib.sha256(token.encode()).hexdigest(),driver_id)).rowcount
            if not changed: reject(404,'DRIVER_NOT_FOUND','Unknown driver')
            db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?',(driver_id,))
            db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
            self._audit(db,driver_id,'development-admin','TOKEN_ROTATED')
        return {'developmentToken':token,'driverId':driver_id}

    def availability(self, driver_id, body):
        if type(body.get('online')) is not bool: reject(400,'INVALID_AVAILABILITY','online must be boolean')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT status FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone()
            if body['online'] and (not row or row[0]!='APPROVED' or not self.ready(db,driver_id)):
                reject(403,'DRIVER_NOT_APPROVED','Admin approval and four approved current documents required')
            if not body['online'] and self.active(db,driver_id): reject(409,'ACTIVE_RIDE','Complete or cancel your active ride before going offline')
            db.execute('UPDATE fleet_drivers SET online=? WHERE id=?',(int(body['online']),driver_id))
            if not body['online']: db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
        return self.status(driver_id)

    def location(self, driver_id, body):
        lat,lng=body.get('latitude'),body.get('longitude')
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lat,lng)) or not -90<=lat<=90 or not -180<=lng<=180:
            reject(400,'INVALID_POSITION','Valid GPS coordinates required')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT online FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone()
            ride=self.active(db,driver_id)
            if not row or (not row[0] and not ride): reject(409,'DRIVER_OFFLINE','Go online to share location')
            now=self.service.clock()
            db.execute('UPDATE fleet_drivers SET lat=?,lng=?,located_ms=? WHERE id=?',(lat,lng,now,driver_id))
            if ride:
                ride['driverPosition']={'latitude':lat,'longitude':lng,'recordedAtEpochMs':now}
                p=ride['draft']['pickup']; distance=self.service.distance_km(lat,lng,p['latitude'],p['longitude'])
                if ride['status']!='TRIP_STARTED': ride['driver']['pickupEtaMinutes']=self.eta(distance)
                ride['updatedAtEpochMs']=now
                db.execute('UPDATE rides SET payload=? WHERE id=?',(json.dumps(ride),ride['id']))
        return {'ok':True}

    def presence(self, driver_id, body):
        # Kept for Build 28 API callers; validate GPS before changing availability.
        if body.get('online'):
            lat,lng=body.get('latitude'),body.get('longitude')
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lat,lng)) or not -90<=lat<=90 or not -180<=lng<=180:
                reject(400,'INVALID_POSITION','Valid GPS coordinates required')
        result=self.availability(driver_id,body)
        if body.get('online'): self.location(driver_id,body)
        return result

    @staticmethod
    def eta(distance): return 1 if distance<=0.2 else max(1,math.ceil(distance/28*60+1))

    def cleanup(self, db):
        now=self.service.clock()
        for d,r in db.execute('SELECT driver_id,ride_id FROM fleet_offers WHERE expires_ms<=?',(now,)).fetchall():
            db.execute('INSERT OR REPLACE INTO fleet_declines VALUES (?,?,?)',(d,r,now+20000))
        db.execute('DELETE FROM fleet_offers WHERE expires_ms<=?',(now,))
        db.execute('DELETE FROM fleet_declines WHERE until_ms<=?',(now,))
        for d,r in db.execute('SELECT driver_id,ride_id FROM fleet_offers').fetchall():
            row=db.execute('SELECT * FROM fleet_drivers WHERE id=?',(d,)).fetchone()
            ride=db.execute('SELECT payload FROM rides WHERE id=?',(r,)).fetchone()
            if not row or not self.eligible(db,row) or not ride or json.loads(ride[0])['status']!='SEARCHING':
                db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(d,))

    def offer(self, driver_id):
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.cleanup(db)
            # Oldest requests first; choose the nearest eligible free driver, independent of poll order.
            drivers=[r for r in db.execute('SELECT * FROM fleet_drivers ORDER BY created_ms,id') if self.eligible(db,r)]
            reserved={r[0] for r in db.execute('SELECT driver_id FROM fleet_offers')}
            claimed={r[0] for r in db.execute('SELECT ride_id FROM fleet_offers')}
            claimed.update(r[0] for r in db.execute('SELECT ride_id FROM driver_offer_state WHERE expires_ms>?',(self.service.clock(),)))
            for ride in sorted(self.rides(db),key=lambda r:(r['requestedAtEpochMs'],r['id'])):
                if ride['status']!='SEARCHING' or ride['id'] in claimed: continue
                p=ride['draft']['pickup']; options=[]
                for d in drivers:
                    if d[0] in reserved or d[4]!=ride['option']['tier']: continue
                    if db.execute('SELECT 1 FROM fleet_declines WHERE driver_id=? AND ride_id=? AND until_ms>?',(d[0],ride['id'],self.service.clock())).fetchone(): continue
                    options.append((self.service.distance_km(d[7],d[8],p['latitude'],p['longitude']),d[0]))
                if options:
                    _,chosen=min(options)
                    db.execute('INSERT INTO fleet_offers VALUES (?,?,?)',(chosen,ride['id'],self.service.clock()+20000))
                    reserved.add(chosen)
            lease=db.execute('SELECT ride_id,expires_ms FROM fleet_offers WHERE driver_id=?',(driver_id,)).fetchone()
            if not lease: return {}
            ride=json.loads(db.execute('SELECT payload FROM rides WHERE id=?',(lease[0],)).fetchone()[0])
            d=db.execute('SELECT * FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone()
            draft,option=ride['draft'],ride['option']; p=draft['pickup']; dest=draft['destination']
            distance=self.service.distance_km(d[7],d[8],p['latitude'],p['longitude'])
            owner=db.execute('SELECT first_name FROM passengers WHERE id=(SELECT owner FROM rides WHERE id=?)',(ride['id'],)).fetchone()
            return {'id':ride['id'],'rideId':ride['id'],'riderName':owner[0] if owner else 'Passenger',
                    'pickup':p,'destination':dest,'pickupName':p['name'],'destinationName':dest['name'],
                    'expiresAtEpochMs':lease[1],'pickupDistanceKm':round(distance,2),'pickupEtaMin':self.eta(distance),
                    'tripDistanceKm':draft['routeEstimate']['distanceKm'],'tripEtaMin':draft['routeEstimate']['durationMinutes'],
                    'fareCad':option['fareCad'],'driverEstimatedEarningsCad':option['breakdown']['driverGrossBeforeCostsCents']/100,'category':option['title']}

    def passenger_availability(self, pickup, tier):
        with self.service.connect() as db:
            reserved={r[0] for r in db.execute('SELECT driver_id FROM fleet_offers WHERE expires_ms>?',(self.service.clock(),))}
            choices=[(self.service.distance_km(r[7],r[8],pickup['latitude'],pickup['longitude']),r[9])
                     for r in db.execute('SELECT * FROM fleet_drivers WHERE category=?',(tier,)) if self.eligible(db,r) and r[0] not in reserved]
        if not choices: return None
        distance,at=min(choices)
        return {'available':True,'etaMinutes':self.eta(distance),'distanceKm':round(distance,2),
                'locationAgeSeconds':max(0,(self.service.clock()-at)//1000),'availableDriverCount':len(choices)}

    def active_ride(self, driver_id):
        with self.service.connect() as db: ride=self.active(db,driver_id)
        if ride: ride.pop('pin',None)
        return ride or {}

    def accept(self, driver_id, ride_id): return self.action(driver_id,ride_id,'accept',{})

    def action(self, driver_id, ride_id, action, body):
        if action not in ('accept','decline','arrive','start','complete','cancel','location'): reject(404,'NOT_FOUND','Unknown action')
        pin_error=False
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record=db.execute('SELECT payload FROM rides WHERE id=?',(ride_id,)).fetchone()
            if not record: reject(404,'RIDE_NOT_FOUND','Unknown ride')
            ride=json.loads(record[0]); now=self.service.clock()
            if action=='accept' and ride.get('fleetDriverId')==driver_id and ride['status']=='DRIVER_ASSIGNED':
                ride.pop('pin',None)
                return ride
            if action in ('accept','decline'):
                lease=db.execute('SELECT expires_ms FROM fleet_offers WHERE driver_id=? AND ride_id=?',(driver_id,ride_id)).fetchone()
                d=db.execute('SELECT * FROM fleet_drivers WHERE id=?',(driver_id,)).fetchone()
                if not lease or lease[0]<=now or ride['status']!='SEARCHING': reject(409,'OFFER_EXPIRED','Offer expired or reassigned')
                if not d or not self.eligible(db,d): reject(409,'DRIVER_UNAVAILABLE','Driver needs approval, fresh GPS and no active trip')
                db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver_id,))
                if action=='decline':
                    db.execute('INSERT OR REPLACE INTO fleet_declines VALUES (?,?,?)',(driver_id,ride_id,now+60000))
                    self._audit(db,driver_id,'driver','DECLINED_'+ride_id)
                    return {'status':'DECLINED'}
                p=ride['draft']['pickup']; dist=self.service.distance_km(d[7],d[8],p['latitude'],p['longitude'])
                ride.update(status='DRIVER_ASSIGNED',fleetDriverId=driver_id,
                    driver={'name':d[1],'vehicle':d[2],'plate':d[3],'rating':5.0,'colour':'','pickupEtaMinutes':self.eta(dist)},
                    driverPosition={'latitude':d[7],'longitude':d[8],'recordedAtEpochMs':d[9]},
                    dispatch={'pickupDistanceKm':round(dist,2),'pickupEtaMinutes':self.eta(dist),'assignedAtEpochMs':now},
                    pin=str(secrets.randbelow(9000)+1000))
            else:
                if ride.get('fleetDriverId')!=driver_id: reject(403,'FORBIDDEN','Ride belongs to another driver')
                target={'arrive':('DRIVER_ASSIGNED','DRIVER_ARRIVED'),'start':('DRIVER_ARRIVED','TRIP_STARTED'),'complete':('TRIP_STARTED','COMPLETED')}
                if action in target and ride['status']==target[action][1]:
                    ride.pop('pin',None); return ride # safe retry after a lost response
                if action=='location':
                    if ride['status'] not in ACTIVE: reject(409,'INVALID_TRANSITION','Ride is no longer active')
                    lat,lng=body.get('latitude'),body.get('longitude')
                    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lat,lng)) or not -90<=lat<=90 or not -180<=lng<=180: reject(400,'INVALID_POSITION','Valid GPS required')
                    ride['driverPosition']={'latitude':lat,'longitude':lng,'recordedAtEpochMs':now}
                    db.execute('UPDATE fleet_drivers SET lat=?,lng=?,located_ms=? WHERE id=?',(lat,lng,now,driver_id))
                elif action=='cancel':
                    if ride['status'] not in ('DRIVER_ASSIGNED','DRIVER_ARRIVED'): reject(409,'INVALID_TRANSITION','Cannot cancel after trip starts')
                    ride['status']='SEARCHING'
                    for key in ('fleetDriverId','driver','driverPosition','pin','dispatch'): ride.pop(key,None)
                    db.execute('INSERT OR REPLACE INTO fleet_declines VALUES (?,?,?)',(driver_id,ride_id,now+60000))
                else:
                    if ride['status']!=target[action][0]: reject(409,'INVALID_TRANSITION','Advance trip states in order')
                    if action=='start':
                        attempt=db.execute('SELECT attempts,until_ms FROM fleet_pin_attempts WHERE ride_id=?',(ride_id,)).fetchone()
                        if attempt and attempt[0]>=5 and attempt[1]>now: reject(429,'PIN_LOCKED','Too many PIN attempts; wait one minute')
                        if not isinstance(body.get('pin'),str) or not secrets.compare_digest(body['pin'],ride['pin']):
                            count=(attempt[0] if attempt and attempt[1]>now else 0)+1
                            db.execute('INSERT OR REPLACE INTO fleet_pin_attempts VALUES (?,?,?)',(ride_id,count,now+60000))
                            pin_error=True
                    if not pin_error:
                        ride['status']=target[action][1]
                        if action=='complete':
                            ride['payment'].update(status='CAPTURED_DEMO',amountCents=ride['option']['breakdown']['totalCents'])
                            self.service.record_development_earning(db,ride)
            if not pin_error:
                ride['updatedAtEpochMs']=now
                db.execute('UPDATE rides SET payload=? WHERE id=?',(json.dumps(ride),ride_id))
                self.service.event(db,ride,driver_id,'FLEET_'+action.upper())
                self._audit(db,driver_id,'driver',action.upper()+'_'+ride_id)
        if pin_error: reject(403,'INVALID_PIN','Ask the passenger for their trip PIN')
        ride.pop('pin',None)
        return ride

    def history(self, driver_id):
        with self.service.connect() as db: rides=self.rides(db)
        trips=[]
        for ride in rides:
            if ride.get('fleetDriverId')!=driver_id or ride['status']!='COMPLETED': continue
            d,o=ride['draft'],ride['option']
            trips.append({'id':ride['id'],'pickup':d['pickup']['name'],'destination':d['destination']['name'],
                          'completedAtEpochMs':ride['updatedAtEpochMs'],'grossFareCad':o['fareCad'],
                          'driverEarningsCad':o['breakdown']['driverGrossBeforeCostsCents']/100,
                          'distanceKm':d['routeEstimate']['distanceKm'],'durationMin':d['routeEstimate']['durationMinutes']})
        return {'trips':sorted(trips,key=lambda r:r['completedAtEpochMs'],reverse=True)}
