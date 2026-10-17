"""Timestamp-aware trip GPS, document revisions and configurable eligibility."""
import base64
import json
import secrets
from datetime import date,datetime
from zoneinfo import ZoneInfo
from fleet35 import Fleet as Previous,FleetError
from fleet28 import reject

class Fleet(Previous):
    document_kinds=('LICENCE','INSURANCE','REGISTRATION','INSPECTION','RECORD_CHECK_CERTIFICATE','DRIVING_RECORD','CRIMINAL_RECORD_CHECK')
    def today(self):return datetime.fromtimestamp(self.service.clock()/1000,ZoneInfo('America/Vancouver')).date().isoformat()
    def required_documents(self,db):
        row=db.execute("SELECT value FROM operation_config44 WHERE name='required_documents'").fetchone()
        return json.loads(row[0]) if row else list(self.document_kinds[:4])
    def ready(self,db,driver):
        if not hasattr(self.service,'operations44'):return super().ready(db,driver)
        docs={r[0]:r[1:] for r in db.execute('SELECT kind,status,expiry_date FROM fleet_documents WHERE driver_id=?',(driver,))}
        return all(k in docs and docs[k][0]=='APPROVED' and docs[k][1] and docs[k][1]>=self.today() for k in self.required_documents(db))
    def documents(self,driver):
        with self.service.connect() as db:
            if not db.execute('SELECT 1 FROM fleet_drivers WHERE id=?',(driver,)).fetchone():return super().documents(driver)
            for k in self.document_kinds[4:]:db.execute("INSERT OR IGNORE INTO fleet_documents(driver_id,kind,status,expiry_date,revision) VALUES (?,?,'NOT_SUBMITTED',NULL,0)",(driver,k))
            required=self.required_documents(db)
        result=super().documents(driver);result['requiredKinds']=required
        for d in result['documents']:d['required']=d['kind'] in required
        return result
    def submit_document(self,driver,kind,body):self.documents(driver);return super().submit_document(driver,kind,body)
    def archive_documents(self,db,driver,kind=None):
        if not hasattr(self.service,'operations44'):return
        q='SELECT kind,status,expiry_date,filename,mime,revision,note,submitted_ms,content FROM fleet_documents WHERE driver_id=?';args=[driver]
        if kind:q+=' AND kind=?';args.append(kind)
        for r in db.execute(q,tuple(args)).fetchall():
            if r[8] is None:continue
            payload=dict(zip(('kind','status','expiryDate','filename','mime','revision','note','submittedAtEpochMs'),r[:8]))
            db.execute('INSERT OR IGNORE INTO document_versions44 VALUES (?,?,?,?,?,?,?)',(secrets.token_hex(16),driver,r[0],r[5],self.service.clock(),json.dumps(payload),r[8]))
    def document_versions(self,driver,kind,revision=None):
        with self.service.connect() as db:rows=db.execute('SELECT revision,at_ms,payload,content FROM document_versions44 WHERE driver_id=? AND kind=? ORDER BY revision DESC',(driver,kind)).fetchall()
        if revision is not None:
            row=next((r for r in rows if r[0]==revision),None)
            if not row:reject(404,'DOCUMENT_NOT_FOUND','Archived version not found')
            return {**json.loads(row[2]),'contentBase64':base64.b64encode(bytes(row[3])).decode()}
        return {'versions':[{**json.loads(r[2]),'archivedAtEpochMs':r[1]} for r in rows]}
    def document_policy(self,actor,b=None):
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if b is not None:
                kinds,reason=b.get('requiredKinds'),b.get('reason')
                if not isinstance(kinds,list) or any(not isinstance(k,str) or k not in self.document_kinds for k in kinds) or not set(self.document_kinds[:4])<=set(kinds) or not isinstance(reason,str) or not 3<=len(reason.strip())<=300:reject(400,'INVALID_POLICY','Keep baseline requirements and provide a reason')
                db.execute("DELETE FROM operation_config44 WHERE name='required_documents'");db.execute("INSERT INTO operation_config44 VALUES ('required_documents',?)",(json.dumps(sorted(set(kinds))),));self.service.operations44.audit(db,actor,'DOCUMENT_POLICY_CHANGED',json.dumps(b))
                for driver, in db.execute('SELECT id FROM fleet_drivers').fetchall():
                    if not self.ready(db,driver):
                        db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?',(driver,));db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver,));self.service.operations44.notify(db,driver,'policy:'+driver+':'+','.join(sorted(kinds)),'DOCUMENT_POLICY','Requirements changed. Open Documents to review your checklist.')
            return dict(requiredKinds=self.required_documents(db),availableKinds=list(self.document_kinds),expiryTimezone='America/Vancouver',publicLaunchApproved=False)
    def document_reminders(self):
        today=date.fromisoformat(self.today())
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE');required=self.required_documents(db)
            for driver,kind,expiry,revision in db.execute('SELECT driver_id,kind,expiry_date,revision FROM fleet_documents').fetchall():
                if not expiry:continue
                days=(date.fromisoformat(expiry)-today).days;t=next((x for x in (-1,0,1,7,14,30) if days<=x),None)
                if t is None:continue
                label='expired' if days<0 else 'expires today' if days==0 else f'expires in {days} days'
                self.service.operations44.notify(db,driver,f'document:{driver}:{kind}:{revision}:{t}','DOCUMENT_EXPIRY',f'{kind.replace("_"," ").title()} {label}. Upload a renewal; review is required.')
                if days<0 and kind in required:
                    db.execute('UPDATE fleet_drivers SET online=0 WHERE id=?',(driver,));db.execute('DELETE FROM fleet_offers WHERE driver_id=?',(driver,))
    def location(self,driver,b):
        if 'observedAtEpochMs' not in b:return super().location(driver,b) # Old clients are excluded from monitoring.
        o=self.service.operations44;p=o.point(b)
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.active(db,driver);supplied=b.get('rideId')
            if supplied and (not r or supplied!=r['id']):
                old=o.ride(db,supplied,driver=driver)
                if old['status'] in ('COMPLETED','CANCELLED_NO_SHOW','CANCELLED_BY_RIDER') and old.get('dispatch',{}).get('assignedAtEpochMs',old['updatedAtEpochMs'])<=p['observedAtEpochMs']<=old['updatedAtEpochMs']:
                    p['late']=True;o.evidence(db,old,driver,'GPS_DRIVER',p,p['observedAtEpochMs']);return {'ok':True,'live':False}
                reject(409,'ASSIGNMENT_CHANGED','Location belongs to another trip')
            row=db.execute('SELECT online,located_ms FROM fleet_drivers WHERE id=?',(driver,)).fetchone()
            if not row or (not row[0] and not r):reject(409,'DRIVER_OFFLINE','Go online to share location')
            p['late']=row[1] is not None and p['observedAtEpochMs']<=row[1]
            if r:
                assigned_at=r.get('dispatch',{}).get('assignedAtEpochMs',r.get('requestedAtEpochMs',self.service.clock()))
                if p['observedAtEpochMs']<assigned_at:
                    reject(409,'ASSIGNMENT_CHANGED','Location predates this assignment')
                o.evidence(db,r,driver,'GPS_DRIVER',p,p['observedAtEpochMs'])
            live=p['quality']=='RELIABLE' and p['fresh'] and not p['late']
            if live:
                db.execute('UPDATE fleet_drivers SET lat=?,lng=?,located_ms=? WHERE id=?',(p['latitude'],p['longitude'],p['observedAtEpochMs'],driver))
                if r:
                    r['driverPosition']={**p,'recordedAtEpochMs':p['observedAtEpochMs']};r['updatedAtEpochMs']=self.service.clock()
                    if r['status']!='TRIP_STARTED':
                        pu=r['draft']['pickup'];r['driver']['pickupEtaMinutes']=self.eta(self.service.distance_km(p['latitude'],p['longitude'],pu['latitude'],pu['longitude']))
                    db.execute('UPDATE rides SET payload=? WHERE id=?',(json.dumps(r),r['id']));o.monitor(db,r,driver,p)
        return {'ok':True,'live':live}
