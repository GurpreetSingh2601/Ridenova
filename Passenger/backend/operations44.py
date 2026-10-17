"""Build 44 safety evidence. Signals support review; no automatic penalties."""
import hashlib
import json
import math
import secrets
from fleet28 import reject

ACTIVE=('DRIVER_ASSIGNED','DRIVER_ARRIVED','TRIP_STARTED')
SCHEMA='''
CREATE TABLE IF NOT EXISTS trip_evidence44(id TEXT PRIMARY KEY,ride_id TEXT NOT NULL,actor TEXT NOT NULL,kind TEXT NOT NULL,observed_ms BIGINT NOT NULL,received_ms BIGINT NOT NULL,payload TEXT NOT NULL,UNIQUE(ride_id,actor,kind,observed_ms));
CREATE INDEX IF NOT EXISTS evidence44_trip ON trip_evidence44(ride_id,observed_ms,id);
CREATE TABLE IF NOT EXISTS trip_monitor44(ride_id TEXT PRIMARY KEY,driver_id TEXT NOT NULL,state TEXT NOT NULL,opened_ms BIGINT NOT NULL,updated_ms BIGINT NOT NULL,best_km REAL NOT NULL,response TEXT NOT NULL,hold_until_ms BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS trip_consent44(ride_id TEXT PRIMARY KEY,owner TEXT NOT NULL,enabled INTEGER NOT NULL,updated_ms BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS trip_shares44(digest TEXT PRIMARY KEY,ride_id TEXT NOT NULL,owner TEXT NOT NULL,expires_ms BIGINT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS trip_holds44(ride_id TEXT PRIMARY KEY,until_ms BIGINT NOT NULL,reason TEXT NOT NULL,actor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS driver_inbox44(id TEXT PRIMARY KEY,driver_id TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,created_ms BIGINT NOT NULL,read_ms BIGINT);
CREATE INDEX IF NOT EXISTS inbox44_driver ON driver_inbox44(driver_id,created_ms);
CREATE TABLE IF NOT EXISTS document_versions44(id TEXT PRIMARY KEY,driver_id TEXT NOT NULL,kind TEXT NOT NULL,revision INTEGER NOT NULL,at_ms BIGINT NOT NULL,payload TEXT NOT NULL,content BLOB,UNIQUE(driver_id,kind,revision));
CREATE TABLE IF NOT EXISTS operation_config44(name TEXT PRIMARY KEY,value TEXT NOT NULL);
'''
class Operations:
    def __init__(self,s):
        self.s=s
        if not s.postgres:
            with s.connect() as db:db.executescript(SCHEMA)
    def evidence(self,db,r,actor,kind,payload,observed=None):
        now=self.s.clock()
        if observed is None:
            last=db.execute('SELECT MAX(observed_ms) FROM trip_evidence44 WHERE ride_id=? AND actor=? AND kind=?',(r['id'],actor,kind)).fetchone()[0]
            observed=max(now,(last or 0)+1)
        db.execute('INSERT OR IGNORE INTO trip_evidence44 VALUES (?,?,?,?,?,?,?)',(secrets.token_hex(16),r['id'],actor,kind,observed,now,json.dumps(payload)))
    def ride(self,db,rid,owner=None,driver=None):
        row=db.execute('SELECT owner,payload FROM rides WHERE id=?',(rid,)).fetchone()
        if not row:reject(404,'RIDE_NOT_FOUND','Trip not found')
        r=json.loads(row[1])
        if owner is not None and owner!=row[0] or driver is not None and driver!=r.get('fleetDriverId'):reject(403,'FORBIDDEN','Trip belongs to another account')
        return r
    def audit(self,db,actor,action,subject):
        db.execute('INSERT INTO admin_audit(at_ms,actor,action,subject) VALUES (?,?,?,?)',(self.s.clock(),actor,action,subject))
    def point(self,b):
        now=self.s.clock();lat,lng,accuracy,at=(b.get(k) for k in ('latitude','longitude','accuracyMeters','observedAtEpochMs'))
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lat,lng,accuracy)) or not -90<=lat<=90 or not -180<=lng<=180 or not 0<=accuracy<=10000:reject(400,'INVALID_POSITION','Valid coordinates and accuracy required')
        if type(at) is not int or not now-86400000<=at<=now+5000:reject(400,'INVALID_TIME','GPS observation time outside allowed range')
        return dict(latitude=lat,longitude=lng,accuracyMeters=accuracy,observedAtEpochMs=at,receivedAtEpochMs=now,quality='RELIABLE' if accuracy<=100 else 'UNCERTAIN',fresh=now-at<=30000)
    def notify(self,db,driver,key,kind,message):
        db.execute('INSERT OR IGNORE INTO driver_inbox44 VALUES (?,?,?,?,?,NULL)',(hashlib.sha256(key.encode()).hexdigest(),driver,kind,message,self.s.clock()))
    def inbox(self,driver,b=None):
        with self.s.connect() as db:
            if b is not None:
                ids=b.get('ids')
                if not isinstance(ids,list) or len(ids)>100 or any(not isinstance(i,str) for i in ids):reject(400,'INVALID_IDS','Invalid notification IDs')
                for i in ids:db.execute('UPDATE driver_inbox44 SET read_ms=? WHERE id=? AND driver_id=?',(self.s.clock(),i,driver))
            rows=db.execute('SELECT id,kind,body,created_ms,read_ms FROM driver_inbox44 WHERE driver_id=? ORDER BY created_ms DESC LIMIT 100',(driver,)).fetchall()
        return {'notifications':[dict(zip(('id','kind','message','createdAtEpochMs','readAtEpochMs'),r)) for r in rows]}
    def monitor(self,db,r,driver,p):
        if r['status']!='DRIVER_ASSIGNED':return
        now=self.s.clock();pickup=r['draft']['pickup'];distance=self.s.distance_km(p['latitude'],p['longitude'],pickup['latitude'],pickup['longitude'])
        row=db.execute('SELECT driver_id,state,opened_ms,updated_ms,best_km,response,hold_until_ms FROM trip_monitor44 WHERE ride_id=?',(r['id'],)).fetchone()
        if not row or row[0]!=driver:
            db.execute('DELETE FROM trip_monitor44 WHERE ride_id=?',(r['id'],));db.execute("INSERT INTO trip_monitor44 VALUES (?,?,'OBSERVING',?,?,?,'',0)",(r['id'],driver,now,now,distance));return
        state,start,best=row[1],row[2],row[4]
        if now-row[3]>60000 or distance<best-0.15:
            if state in ('CHECK_IN','ESCALATED'):self.evidence(db,r,driver,'MONITOR_RESOLVED',{'reason':'Progress resumed or observation reset after GPS gap'})
            db.execute("UPDATE trip_monitor44 SET state='OBSERVING',opened_ms=?,updated_ms=?,best_km=?,response='',hold_until_ms=0 WHERE ride_id=?",(now,now,distance,r['id']));return
        if now<row[6]:db.execute('UPDATE trip_monitor44 SET updated_ms=? WHERE ride_id=?',(now,r['id']));return
        if distance>0.4 and now-start>=180000 and state in ('OBSERVING','ACKNOWLEDGED'):
            state='CHECK_IN';start=now;self.evidence(db,r,driver,'PICKUP_CHECK_IN',{'distanceKm':distance,'basis':'Sustained low progress, not evidence of misconduct'})
            self.notify(db,driver,'check:'+r['id']+':'+str(now),'PICKUP_CHECK_IN','Pickup is taking longer. Check in only when safely stopped.')
        elif state=='CHECK_IN' and now-start>=120000:
            state='ESCALATED';self.evidence(db,r,driver,'PICKUP_ESCALATED',{'reason':'Continued low progress and no response'})
        db.execute('UPDATE trip_monitor44 SET state=?,opened_ms=?,updated_ms=? WHERE ride_id=?',(state,start,now,r['id']))
    def checkin(self,driver,rid,b=None):
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.ride(db,rid,driver=driver)
            row=db.execute('SELECT state,response FROM trip_monitor44 WHERE ride_id=? AND driver_id=?',(rid,driver)).fetchone()
            if b is not None:
                reason=b.get('reason')
                if reason not in ('TRAFFIC','ROAD_CLOSED','NAVIGATION','VEHICLE_PROBLEM','UNABLE','NEED_HELP'):reject(400,'INVALID_RESPONSE','Choose a response')
                if r['status']!='DRIVER_ASSIGNED' or not row or row[0] not in ('CHECK_IN','ACKNOWLEDGED','ESCALATED'):reject(409,'NO_CHECK_IN','No current pickup check-in')
                if row[1]!=reason:
                    state='ESCALATED' if reason in ('UNABLE','VEHICLE_PROBLEM','NEED_HELP') else 'ACKNOWLEDGED'
                    db.execute('UPDATE trip_monitor44 SET state=?,response=?,hold_until_ms=? WHERE ride_id=?',(state,reason,self.s.clock()+300000,rid));self.evidence(db,r,driver,'DRIVER_RESPONSE',{'reason':reason});row=(state,reason)
            return {'state':row[0] if row and r['status']=='DRIVER_ASSIGNED' else 'NONE','response':row[1] if row else '', 'automaticReassignment':False}
    def route(self,driver,rid,b):
        pts=b.get('points');leg=b.get('leg');dist=b.get('distanceMeters');duration=b.get('durationSeconds')
        if leg not in ('PICKUP','TRIP') or not isinstance(pts,list) or not 2<=len(pts)<=300 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<1000000 for v in (dist,duration)):reject(400,'INVALID_ROUTE','Route leg, distance, time and 2–300 points required')
        for p in pts:
            if not isinstance(p,dict) or any(type(p.get(k)) not in (int,float) or not math.isfinite(p[k]) for k in ('latitude','longitude')) or not -90<=p['latitude']<=90 or not -180<=p['longitude']<=180:reject(400,'INVALID_ROUTE','Invalid route coordinates')
        route={'points':pts,'leg':leg,'distanceMeters':dist,'durationSeconds':duration,'source':'DRIVER_NAVIGATION','estimated':True};digest=hashlib.sha256(json.dumps(route,sort_keys=True).encode()).hexdigest();route['digest']=digest
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.ride(db,rid,driver=driver)
            if r['status'] not in ACTIVE:reject(409,'TRIP_ENDED','Trip ended')
            previous=db.execute("SELECT payload FROM trip_evidence44 WHERE ride_id=? AND actor=? AND kind='ROUTE_SNAPSHOT' ORDER BY observed_ms DESC LIMIT 1",(rid,driver)).fetchone()
            if not previous or json.loads(previous[0]).get('digest')!=digest:self.evidence(db,r,driver,'ROUTE_SNAPSHOT',route)
        return {'ok':True}
    def consent(self,owner,rid,b=None):
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.ride(db,rid,owner=owner)
            if b is not None:
                enabled=b.get('enabled')
                if type(enabled) is not bool:reject(400,'INVALID_CONSENT','Choose whether to share location')
                if enabled and r['status'] not in ACTIVE:reject(409,'NOT_ACTIVE','Sharing requires an active trip')
                db.execute('DELETE FROM trip_consent44 WHERE ride_id=?',(rid,));db.execute('INSERT INTO trip_consent44 VALUES (?,?,?,?)',(rid,owner,int(enabled),self.s.clock()))
                self.evidence(db,r,owner,'PASSENGER_CONSENT',{'enabled':enabled})
                if not enabled:db.execute("DELETE FROM trip_evidence44 WHERE ride_id=? AND kind='GPS_PASSENGER'",(rid,))
            row=db.execute('SELECT enabled FROM trip_consent44 WHERE ride_id=?',(rid,)).fetchone()
        return {'enabled':bool(row and row[0] and r['status'] in ACTIVE)}
    def passenger_point(self,owner,rid,b):
        p=self.point(b)
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.ride(db,rid,owner=owner);c=db.execute('SELECT enabled FROM trip_consent44 WHERE ride_id=? AND owner=?',(rid,owner)).fetchone()
            if r['status'] not in ACTIVE or not c or not c[0]:reject(403,'CONSENT_REQUIRED','Active trip and consent required')
            self.evidence(db,r,owner,'GPS_PASSENGER',p,p['observedAtEpochMs'])
        return {'ok':True}
    def share(self,owner,rid,b):
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.ride(db,rid,owner=owner);action=b.get('action')
            if action not in ('create','revoke'):reject(400,'INVALID_ACTION','Choose create or revoke')
            db.execute('UPDATE trip_shares44 SET revoked=1 WHERE ride_id=? AND owner=?',(rid,owner))
            if action=='revoke':self.evidence(db,r,owner,'SHARE_REVOKED',{});return {'revoked':True}
            if r['status'] not in ACTIVE:reject(409,'NOT_ACTIVE','Share an active trip')
            token=secrets.token_urlsafe(32);expires=self.s.clock()+4*3600000
            db.execute('INSERT INTO trip_shares44 VALUES (?,?,?,?,0)',(hashlib.sha256(token.encode()).hexdigest(),rid,owner,expires));self.evidence(db,r,owner,'SHARE_CREATED',{'expiresAtEpochMs':expires})
        return {'token':token,'expiresAtEpochMs':expires}
    def public_share(self,token):
        if not isinstance(token,str) or not 20<=len(token)<=100:reject(404,'LINK_UNAVAILABLE','Link unavailable')
        with self.s.connect() as db:
            row=db.execute('SELECT ride_id FROM trip_shares44 WHERE digest=? AND revoked=0 AND expires_ms>?',(hashlib.sha256(token.encode()).hexdigest(),self.s.clock())).fetchone()
            if not row:reject(404,'LINK_UNAVAILABLE','Link expired or revoked')
            r=self.ride(db,row[0])
            if r['status'] not in ACTIVE:reject(410,'TRIP_ENDED','Trip has ended')
            return {'status':r['status'],'destination':r['draft']['destination'],'driverPosition':self.latest(db,r,'GPS_DRIVER'),'serverTimeEpochMs':self.s.clock()}
    def latest(self,db,r,kind):
        q='SELECT payload FROM trip_evidence44 WHERE ride_id=? AND kind=?';args=[r['id'],kind]
        if kind=='GPS_DRIVER':q+=' AND actor=?';args.append(r.get('fleetDriverId',''))
        row=db.execute(q+' ORDER BY observed_ms DESC LIMIT 1',tuple(args)).fetchone()
        return json.loads(row[0]) if row else None
    def live(self,actor):
        with self.s.connect() as db:
            result=[]
            for (payload,) in db.execute('SELECT payload FROM rides'):
                r=json.loads(payload)
                if r['status'] not in ACTIVE:continue
                m=db.execute('SELECT state,response FROM trip_monitor44 WHERE ride_id=? AND driver_id=?',(r['id'],r.get('fleetDriverId',''))).fetchone()
                result.append(dict(id=r['id'],status=r['status'],pickup=r['draft']['pickup'],destination=r['draft']['destination'],driverId=r.get('fleetDriverId'),driver=r.get('driver'),driverPosition=self.latest(db,r,'GPS_DRIVER'),passengerPosition=self.latest(db,r,'GPS_PASSENGER'),monitor=dict(state=m[0],response=m[1]) if m else None))
                if len(result)>=100:break
            self.audit(db,actor,'LIVE_TRIPS_VIEW','active')
        return {'rides':result,'serverTimeEpochMs':self.s.clock(),'automaticReassignment':False,'limit':100}
    def detail(self,actor,rid,cursor=0):
        with self.s.connect() as db:
            r=self.ride(db,rid);rows=db.execute('SELECT id,actor,kind,observed_ms,received_ms,payload FROM trip_evidence44 WHERE ride_id=? ORDER BY observed_ms,id LIMIT 1001 OFFSET ?',(rid,cursor)).fetchall()
            events=db.execute('SELECT sequence,at_ms,type,payload FROM events WHERE ride_id=? ORDER BY sequence',(rid,)).fetchall();hold=db.execute('SELECT until_ms,reason FROM trip_holds44 WHERE ride_id=?',(rid,)).fetchone();self.audit(db,actor,'TRIP_EVIDENCE_VIEW',rid)
        return dict(rideId=rid,status=r['status'],driverId=r.get('fleetDriverId'),pickup=r['draft']['pickup'],destination=r['draft']['destination'],plannedRoute=r['draft'].get('routeEstimate'),evidence=[dict(id=x[0],actor=x[1],kind=x[2],observedAtEpochMs=x[3],receivedAtEpochMs=x[4],data=json.loads(x[5])) for x in rows[:1000]],nextCursor=cursor+1000 if len(rows)>1000 else None,events=[dict(sequence=x[0],atEpochMs=x[1],type=x[2],data=json.loads(x[3])) for x in events],hold=dict(untilEpochMs=hold[0],reason=hold[1]) if hold else None)
    def reassign(self,actor,rid,b):
        driver=b.get('expectedDriverId');reason=b.get('reason')
        if not isinstance(driver,str) or not isinstance(reason,str) or not 3<=len(reason.strip())<=300:reject(400,'REASON_REQUIRED','Expected driver and reason required')
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.ride(db,rid)
            previous=db.execute("SELECT payload FROM trip_evidence44 WHERE ride_id=? AND kind='ADMIN_REASSIGN'",(rid,)).fetchall()
            if any(json.loads(x[0]).get('previousDriverId')==driver for x in previous):return {'status':'ALREADY_REASSIGNED'}
            if r['status'] not in ('DRIVER_ASSIGNED','DRIVER_ARRIVED') or r.get('fleetDriverId')!=driver:reject(409,'TRIP_CHANGED','Trip started or assignment changed')
            self.evidence(db,r,actor,'ADMIN_REASSIGN',dict(previousDriverId=driver,reason=reason.strip(),fareUnchanged=True))
            r['status']='SEARCHING';r['updatedAtEpochMs']=self.s.clock()
            for key in ('fleetDriverId','driver','driverPosition','pin','dispatch','waiting'):r.pop(key,None)
            db.execute('UPDATE rides SET payload=? WHERE id=?',(json.dumps(r),rid))
            for table in ('fleet_offers','fleet_radar_candidates','fleet_pin_attempts','trip_monitor44'):db.execute('DELETE FROM '+table+' WHERE ride_id=?',(rid,))
            db.execute("UPDATE fleet_radar SET status='FALLBACK' WHERE ride_id=?",(rid,));db.execute('INSERT OR REPLACE INTO fleet_declines VALUES (?,?,?)',(driver,rid,9223372036854775807))
            self.s.event(db,r,actor,'ADMIN_REASSIGN');self.audit(db,actor,'RIDE_REASSIGNED',rid);self.notify(db,driver,'reassign:'+rid,'ASSIGNMENT_CHANGED','Pickup reassigned. Do not start this trip. Refresh RideNova.')
        return {'status':'SEARCHING','fareUnchanged':True}
    def hold(self,actor,rid,b):
        days,reason=b.get('days'),b.get('reason')
        if type(days) is not int or not 0<=days<=90 or not isinstance(reason,str) or not 3<=len(reason.strip())<=300:reject(400,'INVALID_HOLD','Reason and 0–90 days required')
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.ride(db,rid);db.execute('DELETE FROM trip_holds44 WHERE ride_id=?',(rid,))
            if days:db.execute('INSERT INTO trip_holds44 VALUES (?,?,?,?)',(rid,self.s.clock()+days*86400000,reason,actor))
            self.audit(db,actor,'EVIDENCE_HOLD_CHANGED',rid)
        return {'heldDays':days}
    def maintain(self):
        now=self.s.clock()
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE');db.execute("DELETE FROM trip_evidence44 WHERE kind='ROUTE_SNAPSHOT' AND received_ms<?",(now-30*86400000,));db.execute('DELETE FROM trip_holds44 WHERE until_ms<=?',(now,));protected={x[0] for x in db.execute('SELECT ride_id FROM trip_holds44')};drivers=set()
            for (payload,) in db.execute('SELECT payload FROM rides'):
                r=json.loads(payload)
                if r['id'] in protected or r['status'] in ACTIVE:
                    if r.get('fleetDriverId'):drivers.add(r['fleetDriverId'])
                    continue
                db.execute("DELETE FROM trip_evidence44 WHERE ride_id=? AND kind IN ('GPS_DRIVER','GPS_PASSENGER','ROUTE_SNAPSHOT') AND received_ms<?",(r['id'],now-30*86400000))
                db.execute('DELETE FROM trip_evidence44 WHERE ride_id=? AND received_ms<?',(r['id'],now-365*86400000))
            for driver, in db.execute('SELECT DISTINCT driver_id FROM document_versions44').fetchall():
                if driver not in drivers:db.execute('DELETE FROM document_versions44 WHERE driver_id=? AND at_ms<?',(driver,now-365*86400000))
            db.execute('DELETE FROM driver_inbox44 WHERE created_ms<?',(now-90*86400000,));db.execute('DELETE FROM trip_shares44 WHERE expires_ms<=? OR revoked=1',(now,))
        self.s.fleet.document_reminders()
