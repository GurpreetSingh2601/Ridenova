"""Build 44 evidence, concurrency, privacy, eligibility and HTTP authorization."""
import json
import threading
import unittest
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
import test_build29 as previous
from server import Service,make_handler
from staff38 import Staff,PERMS
from fleet28 import FleetError

class Build44Tests(unittest.TestCase):
    setUp=previous.Build29Tests.setUp
    tearDown=previous.Build29Tests.tearDown
    register=previous.Build29Tests.register
    document=previous.Build29Tests.document
    book=previous.Build29Tests.book
    assigned=previous.Build29Tests.assigned
    error=previous.Build29Tests.error
    def point(self,**kw):return dict(latitude=49.28,longitude=-123.12,accuracyMeters=8,observedAtEpochMs=self.now,**kw)
    def ops(self):Staff(self.service.database);return self.service.operations44
    def test_gps_persists_and_duplicate_upload_has_one_sample(self):
        d,r=self.assigned();self.now+=1000
        for _ in range(2):self.fleet.location(d,self.point())
        s=Service(self.service.database,clock=lambda:self.now);Staff(s.database)
        self.assertEqual(sum(x['kind']=='GPS_DRIVER' for x in s.operations44.detail('owner',r)['evidence']),1)
    def test_stale_or_uncertain_gps_does_not_refresh_dispatch(self):
        d,r=self.assigned();self.now+=60000
        for b in ({**self.point(),'observedAtEpochMs':self.now-45000},{**self.point(),'accuracyMeters':500}):self.assertFalse(self.fleet.location(d,b)['live'])
        self.assertEqual(self.fleet.status(d)['lastLocation']['ageSeconds'],60)
    def test_future_invalid_and_wrong_trip_samples_rejected(self):
        d,r=self.assigned()
        self.error('INVALID_TIME',lambda:self.fleet.location(d,{**self.point(),'observedAtEpochMs':self.now+6000}))
        self.error('INVALID_POSITION',lambda:self.fleet.location(d,{**self.point(),'latitude':float('nan')}))
        self.error('RIDE_NOT_FOUND',lambda:self.fleet.location(d,self.point(rideId='old')))
    def test_pre_assignment_sample_cannot_be_attached_to_new_trip(self):
        d,r=self.assigned()
        before=self.fleet.status(d)['lastLocation']
        for extra in ({},{'rideId':r}):
            sample={**self.point(),**extra,'observedAtEpochMs':self.now-1000}
            self.error('ASSIGNMENT_CHANGED',lambda:self.fleet.location(d,sample))
        self.assertFalse(any(e['kind']=='GPS_DRIVER' for e in self.ops().detail('owner',r)['evidence']))
        self.assertEqual(self.fleet.status(d)['lastLocation'],before)
    def test_consent_is_scoped_revocable_and_required(self):
        d,r=self.assigned();o=self.ops()
        self.error('CONSENT_REQUIRED',lambda:o.passenger_point('p',r,self.point()))
        self.error('FORBIDDEN',lambda:o.consent('someone',r,{'enabled':True}))
        o.consent('p',r,{'enabled':True});o.passenger_point('p',r,self.point());self.assertTrue(any(e['kind']=='GPS_PASSENGER' for e in o.detail('owner',r)['evidence']))
        o.consent('p',r,{'enabled':False});self.assertFalse(any(e['kind']=='GPS_PASSENGER' for e in o.detail('owner',r)['evidence']))
    def test_shares_hash_revoke_expire_and_hide_private_fields(self):
        d,r=self.assigned();o=self.ops();token=o.share('p',r,{'action':'create'})['token']
        with self.service.connect() as db:self.assertNotEqual(db.execute('SELECT digest FROM trip_shares44').fetchone()[0],token)
        data=o.public_share(token);self.assertEqual(set(data),{'status','destination','driverPosition','serverTimeEpochMs'})
        o.share('p',r,{'action':'revoke'});self.error('LINK_UNAVAILABLE',lambda:o.public_share(token))
        token=o.share('p',r,{'action':'create'})['token'];self.now+=4*3600000+1;self.error('LINK_UNAVAILABLE',lambda:o.public_share(token))
    def test_trip_end_invalidates_share(self):
        d,r=self.assigned();o=self.ops();token=o.share('p',r,{'action':'create'})['token'];self.service.cancel('p',r)
        self.error('TRIP_ENDED',lambda:o.public_share(token))
    def test_atomic_reassignment_preserves_price_and_blocks_old_driver(self):
        d,r=self.assigned();o=self.ops();before=self.service.get('p',r)
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:o.reassign('owner',r,{'expectedDriverId':d,'reason':'Driver confirmed unable to arrive'}),range(2)))
        self.assertEqual(sorted(x['status'] for x in results),['ALREADY_REASSIGNED','SEARCHING']);self.assertEqual(before['option'],self.service.get('p',r)['option'])
        self.error('FORBIDDEN',lambda:self.fleet.action(d,r,'start',{'pin':before['pin']}));self.assertEqual(self.fleet.offer(d),{})
    def test_reassign_refuses_started_trip(self):
        d,r=self.assigned();self.fleet.action(d,r,'arrive',{});self.fleet.action(d,r,'start',{'pin':self.service.get('p',r)['pin']})
        self.error('TRIP_CHANGED',lambda:self.ops().reassign('owner',r,{'expectedDriverId':d,'reason':'Must refuse'}))
    def test_versions_and_reminder_retries(self):
        d=self.register()['driverId'];o=self.ops();self.fleet.submit_document(d,'LICENCE',self.document(2))
        self.assertEqual([v['revision'] for v in self.fleet.document_versions(d,'LICENCE')['versions']],[2,1])
        with self.service.connect() as db:db.execute("UPDATE fleet_documents SET expiry_date='2026-09-16' WHERE driver_id=? AND kind='LICENCE'",(d,))
        for _ in range(2):self.fleet.document_reminders()
        self.assertEqual(len(o.inbox(d)['notifications']),1);self.assertFalse(self.fleet.status(d)['documentsReady'])
    def test_expired_document_blocks_start_but_completion_remains_available(self):
        d,r=self.assigned();self.fleet.action(d,r,'arrive',{})
        with self.service.connect() as db:db.execute("UPDATE fleet_documents SET expiry_date='2020-01-01' WHERE driver_id=? AND kind='LICENCE'",(d,))
        self.error('DOCUMENTS_REQUIRED',lambda:self.fleet.action(d,r,'start',{'pin':self.service.get('p',r)['pin']}))
        with self.service.connect() as db:db.execute("UPDATE fleet_documents SET expiry_date='2027-09-18' WHERE driver_id=? AND kind='LICENCE'",(d,))
        self.fleet.action(d,r,'start',{'pin':self.service.get('p',r)['pin']})
        with self.service.connect() as db:db.execute("UPDATE fleet_documents SET expiry_date='2020-01-01' WHERE driver_id=? AND kind='LICENCE'",(d,))
        self.fleet.document_reminders();self.fleet.action(d,r,'complete',{});self.assertEqual(self.service.get('p',r)['status'],'COMPLETED')
    def test_policy_enforces_extra_documents_without_silent_default_change(self):
        d=self.register()['driverId'];self.ops();self.assertTrue(self.fleet.status(d)['documentsReady'])
        required=list(self.fleet.document_kinds[:4])+['RECORD_CHECK_CERTIFICATE'];self.fleet.document_policy('owner',{'requiredKinds':required,'reason':'Compliance review'})
        self.assertFalse(self.fleet.status(d)['documentsReady']);self.assertFalse(self.fleet.status(d)['online'])
        self.fleet.submit_document(d,'RECORD_CHECK_CERTIFICATE',self.document());self.fleet.review_document(d,'RECORD_CHECK_CERTIFICATE',{'revision':1,'status':'APPROVED'})
        self.assertTrue(self.fleet.status(d)['documentsReady'])
    def test_hold_retains_gps_and_release_allows_cleanup(self):
        d,r=self.assigned();o=self.ops();self.now+=1;self.fleet.location(d,self.point());o.hold('owner',r,{'reason':'Safety case','days':90});self.service.cancel('p',r);self.now+=31*86400000;o.maintain()
        self.assertTrue(any(x['kind']=='GPS_DRIVER' for x in o.detail('owner',r)['evidence']));o.hold('owner',r,{'reason':'Case resolved','days':0});o.maintain();self.assertFalse(any(x['kind']=='GPS_DRIVER' for x in o.detail('owner',r)['evidence']))
    def test_checkin_continuous_observation_response_and_gap(self):
        d,r=self.assigned();o=self.ops()
        for _ in range(21):self.now+=10000;self.fleet.location(d,{**self.point(),'latitude':49.30})
        self.assertEqual(o.checkin(d,r)['state'],'CHECK_IN');o.checkin(d,r,{'reason':'TRAFFIC'});self.assertEqual(o.checkin(d,r)['state'],'ACKNOWLEDGED')
        self.now+=70000;self.fleet.location(d,{**self.point(),'latitude':49.30});self.assertEqual(o.checkin(d,r)['state'],'OBSERVING')
    def test_unanswered_checkin_escalates_without_reassignment_or_penalty(self):
        d,r=self.assigned();o=self.ops();before=self.service.get('p',r)['option']
        for _ in range(34):self.now+=10000;self.fleet.location(d,{**self.point(),'latitude':49.30})
        self.assertEqual(o.checkin(d,r)['state'],'ESCALATED');trip=self.service.get('p',r);self.assertEqual(trip['fleetDriverId'],d);self.assertEqual(trip['option'],before)
    def test_route_snapshots_validate_and_dedupe(self):
        d,r=self.assigned();o=self.ops();body={'leg':'PICKUP','distanceMeters':500,'durationSeconds':100,'points':[{'latitude':49.28,'longitude':-123.12},{'latitude':49.281,'longitude':-123.12}]}
        o.route(d,r,body);o.route(d,r,body);self.assertEqual(sum(e['kind']=='ROUTE_SNAPSHOT' for e in o.detail('owner',r)['evidence']),1)
        self.error('INVALID_ROUTE',lambda:o.route(d,r,{**body,'durationSeconds':float('nan')}))
    def test_ended_trip_accepts_only_original_window_backfill(self):
        d,r=self.assigned();self.now+=1000;p=self.point(rideId=r);self.fleet.action(d,r,'arrive',{});self.fleet.action(d,r,'start',{'pin':self.service.get('p',r)['pin']});self.now+=1000;self.fleet.action(d,r,'complete',{})
        self.now+=1000;self.assertFalse(self.fleet.location(d,p)['live']);self.error('ASSIGNMENT_CHANGED',lambda:self.fleet.location(d,self.point(rideId=r)))
    def test_accurate_backfill_remains_historical_not_live(self):
        d,r=self.assigned();self.now+=60000
        b={**self.point(),'observedAtEpochMs':self.now-45000}
        self.assertFalse(self.fleet.location(d,b)['live'])
        e=next(x for x in self.ops().detail('owner',r)['evidence'] if x['kind']=='GPS_DRIVER')
        self.assertEqual(e['data']['quality'],'RELIABLE');self.assertFalse(e['data']['fresh'])
    def test_inbox_read_cannot_modify_another_driver(self):
        first=self.register()['driverId'];second=self.register()['driverId'];o=self.ops()
        with self.service.connect() as db:o.notify(db,first,'owned-notice','DOCUMENT_EXPIRY','Test reminder')
        item=o.inbox(first)['notifications'][0];o.inbox(second,{'ids':[item['id']]})
        self.assertIsNone(o.inbox(first)['notifications'][0]['readAtEpochMs'])
        o.inbox(first,{'ids':[item['id']]});self.assertIsNotNone(o.inbox(first)['notifications'][0]['readAtEpochMs'])
    def test_provider_route_cache_expires_even_under_hold(self):
        d,r=self.assigned();o=self.ops()
        o.route(d,r,{'leg':'TRIP','distanceMeters':500,'durationSeconds':100,'points':[{'latitude':49.28,'longitude':-123.12},{'latitude':49.281,'longitude':-123.12}]})
        o.hold('owner',r,{'days':90,'reason':'Retain actual GPS only'});self.now+=31*86400000;o.maintain()
        self.assertFalse(any(e['kind']=='ROUTE_SNAPSHOT' for e in o.detail('owner',r)['evidence']))
    def test_http_tracking_rbac_driver_isolation_and_audit(self):
        d,r=self.assigned();handler=make_handler(self.service);staff=Staff(self.service.database);tokens={}
        with staff.connect() as db:
            for role in ('OWNER','SUPPORT','FINANCE','COMPLIANCE'):staff._create(db,role.lower(), 'long-test-password-only',role,'bootstrap')
        for role in ('OWNER','SUPPORT','FINANCE','COMPLIANCE'):tokens[role]=staff.login({'username':role.lower(),'password':'long-test-password-only'})['accessToken']
        http=ThreadingHTTPServer(('127.0.0.1',0),handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        def call(path,role,body=None):
            req=urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+tokens.get(role,'invalid'),'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=5) as response:return response.status,json.load(response)
            except urllib.error.HTTPError as e:return e.code,json.load(e)
        try:
            tokens['DRIVER']=self.register()['developmentToken']
            self.assertEqual(call('/v3/operations/driver/rides/'+r+'/check-in','DRIVER')[0],403)
            self.assertEqual(call('/v3/operations/driver/documents/LICENCE','DRIVER')[0],200)
            self.assertEqual(call('/v3/operations/driver/documents/LICENCE','bad')[0],401)
            self.assertEqual(set(call('/map-config','bad')[1]),{'browserKey'})
            for role in ('FINANCE','COMPLIANCE'):self.assertEqual(call('/v3/operations/admin/live',role)[0],403)
            self.assertEqual(call('/v3/operations/admin/live','SUPPORT')[0],200)
            self.assertEqual(call('/v3/operations/admin/rides/'+r+'/hold','SUPPORT',{'days':90,'reason':'No permission'})[0],403)
            self.assertEqual(call('/v3/operations/admin/rides/'+r+'/evidence','OWNER')[0],200)
            self.assertEqual(call('/v3/operations/admin/live','bad')[0],401)
            self.assertTrue(any(x['action']=='TRIP_EVIDENCE_VIEW' for x in staff.audit()['events']))
        finally:http.shutdown();http.server_close();thread.join()

if __name__=='__main__':unittest.main()
