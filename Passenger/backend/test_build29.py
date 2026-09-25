import base64
from contextlib import closing
import json
import os
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from server import Service, make_handler
from fleet29 import FleetError, KINDS

class Build29Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.now=int(datetime(2026,9,18,tzinfo=timezone.utc).timestamp()*1000)
        self.service=Service(self.tmp.name+'/db.sqlite',clock=lambda:self.now)
        self.fleet=self.service.fleet
        self.request={'pickup':{'name':'A','address':'Vancouver','latitude':49.28,'longitude':-123.12},'destination':{'name':'B','address':'Burnaby','latitude':49.25,'longitude':-122.98},'scheduled':False}
    def tearDown(self): self.tmp.cleanup()
    def register(self,ready=True,lat=49.28,category='ECONOMY'):
        reg=self.fleet.register({'name':'Test Driver','vehicle':'Test vehicle','plate':'TEST','category':category})
        d=reg['driverId']
        if ready:
            for kind in KINDS:
                self.fleet.submit_document(d,kind,self.document())
                self.fleet.review_document(d,kind,{'revision':1,'status':'APPROVED'})
            self.fleet.approve(d,{'status':'APPROVED'})
            self.fleet.presence(d,{'online':True,'latitude':lat,'longitude':-123.12})
        return reg
    def document(self,revision=0):
        return {'filename':'sample.pdf','mime':'application/pdf','expiryDate':'2027-09-18','revision':revision,'contentBase64':base64.b64encode(b'%PDF-1.4\nSample test file\n%%EOF').decode()}
    def book(self,owner='p',tier='ECONOMY'):
        q=self.service.quote(owner,self.request)
        return self.service.create(owner,{'quoteToken':q['quoteToken'],'rideOption':{'tier':tier}})
    def error(self,code,fn):
        with self.assertRaises(FleetError) as ctx: fn()
        self.assertEqual(ctx.exception.code,code)
    def assigned(self):
        d=self.register()['driverId']; r=self.book(); self.fleet.offer(d); self.fleet.accept(d,r['id']); return d,r['id']
    def test_onboarding_requires_all_current_reviews(self):
        d=self.register(False)['driverId']
        self.error('DOCUMENTS_REQUIRED',lambda:self.fleet.approve(d,{'status':'APPROVED'}))
        self.error('DRIVER_NOT_APPROVED',lambda:self.fleet.availability(d,{'online':True}))
        self.fleet.submit_document(d,'LICENCE',self.document())
        self.error('DOCUMENTS_REQUIRED',lambda:self.fleet.approve(d,{'status':'APPROVED'}))
    def test_document_validation_and_revision_conflicts(self):
        d=self.register(False)['driverId']
        for field,value in [('filename','../bad.pdf'),('mime','text/html'),('contentBase64','!invalid'),('expiryDate','2020-01-01')]:
            body=self.document();body[field]=value
            with self.assertRaises(FleetError): self.fleet.submit_document(d,'LICENCE',body)
        self.fleet.submit_document(d,'LICENCE',self.document())
        self.error('DOCUMENT_CHANGED',lambda:self.fleet.submit_document(d,'LICENCE',self.document()))
        self.error('DOCUMENT_CHANGED',lambda:self.fleet.review_document(d,'LICENCE',{'revision':0,'status':'APPROVED'}))
        self.error('INVALID_REVIEW',lambda:self.fleet.review_document(d,'LICENCE',{'revision':1,'status':'REJECTED'}))
        self.fleet.review_document(d,'LICENCE',{'revision':1,'status':'REJECTED','note':'Unreadable'})
        self.fleet.submit_document(d,'LICENCE',self.document(2))
        docs=self.fleet.documents(d)['documents'];doc=next(x for x in docs if x['kind']=='LICENCE')
        self.assertEqual(doc['status'],'PENDING');self.assertIsNone(doc['note']);self.assertEqual(doc['revision'],3)
    def test_nearest_driver_selected_regardless_of_poll_order(self):
        near=self.register()['driverId'];far=self.register(lat=49.35)['driverId'];r=self.book()
        self.assertEqual(self.fleet.offer(far),{})
        offer=self.fleet.offer(near);self.assertEqual(offer['id'],r['id'])
        self.assertEqual(self.fleet.offer(near),offer)
        for field in ('pickup','destination','fareCad','driverEstimatedEarningsCad','category'): self.assertIn(field,offer)
    def test_expired_offer_reassigned_without_original_driver_polling(self):
        a=self.register()['driverId'];b=self.register(lat=49.30)['driverId'];r=self.book()
        self.fleet.offer(a);self.now+=20001
        self.assertEqual(self.fleet.offer(b)['id'],r['id'])
        self.error('OFFER_EXPIRED',lambda:self.fleet.accept(a,r['id']))
    def test_stale_gps_excluded_at_accept_and_availability(self):
        d=self.register()['driverId'];r=self.book();self.fleet.offer(d);self.now+=30001
        self.assertFalse(self.service.passenger_availability({'pickup':self.request['pickup'],'tier':'ECONOMY'})['available'])
        with self.assertRaises(FleetError): self.fleet.accept(d,r['id'])
    def test_category_and_busy_driver_exclusion(self):
        d=self.register(category='XL')['driverId'];self.book()
        self.assertEqual(self.fleet.offer(d),{})
        q=self.service.passenger_availability({'pickup':self.request['pickup'],'tier':'ECONOMY'})
        self.assertFalse(q['available'])
        r=self.book('second','XL');self.fleet.offer(d);self.fleet.accept(d,r['id']);self.book('third','XL')
        self.assertEqual(self.fleet.offer(d),{})
    def test_two_concurrent_drivers_cannot_accept_same_ride(self):
        a=self.register()['driverId'];b=self.register(lat=49.31)['driverId'];r=self.book();self.fleet.offer(a)
        def accept(d):
            try: self.fleet.accept(d,r['id']);return True
            except FleetError:return False
        with ThreadPoolExecutor(2) as pool: self.assertEqual(sum(pool.map(accept,[a,b])),1)
        self.assertEqual(self.service.get('p',r['id'])['fleetDriverId'],a)
    def test_complete_lifecycle_gps_pin_isolation_earnings_retry(self):
        d,r=self.assigned();other=self.register()['driverId']
        self.assertEqual(self.fleet.accept(d,r)['id'],r)
        snapshot=self.fleet.active_ride(d);self.assertNotIn('pin',snapshot)
        for field in ('rating','colour','pickupEtaMinutes','name','vehicle','plate'): self.assertIn(field,snapshot['driver'])
        self.error('FORBIDDEN',lambda:self.fleet.action(other,r,'arrive',{}))
        self.fleet.location(d,{'latitude':49.29,'longitude':-123.11})
        self.assertEqual(self.service.get('p',r)['driverPosition']['latitude'],49.29)
        self.fleet.action(d,r,'arrive',{})
        self.error('INVALID_PIN',lambda:self.fleet.action(d,r,'start',{'pin':'bad'}))
        pin=self.service.get('p',r)['pin'];self.fleet.action(d,r,'start',{'pin':pin});self.fleet.action(d,r,'complete',{})
        self.fleet.action(d,r,'complete',{})
        self.assertEqual(len(self.fleet.history(d)['trips']),1);self.assertEqual(self.fleet.history(other)['trips'],[])
        with self.service.connect() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM development_earnings').fetchone()[0],1)
        self.assertEqual(self.fleet.active_ride(d),{})
        self.assertEqual(self.service.get('p',r)['payment']['status'],'CAPTURED_DEMO')
    def test_pin_attempts_persist_and_lock(self):
        d,r=self.assigned();self.fleet.action(d,r,'arrive',{})
        for _ in range(5): self.error('INVALID_PIN',lambda:self.fleet.action(d,r,'start',{'pin':'bad'}))
        pin=self.service.get('p',r)['pin']
        self.error('PIN_LOCKED',lambda:self.fleet.action(d,r,'start',{'pin':pin}))
        self.now+=60001;self.fleet.action(d,r,'start',{'pin':pin})
    def test_cancel_requeues_and_clears_driver_data(self):
        d,r=self.assigned();b=self.register()['driverId'];self.fleet.action(d,r,'cancel',{})
        ride=self.service.get('p',r)
        for key in ('pin','driver','fleetDriverId','dispatch','driverPosition'):self.assertNotIn(key,ride)
        self.assertEqual(self.fleet.offer(d),{});self.assertEqual(self.fleet.offer(b)['id'],r)
    def test_passenger_cancel_releases_offer(self):
        d=self.register()['driverId'];r=self.book();self.fleet.offer(d);self.service.cancel('p',r['id'])
        self.assertEqual(self.fleet.offer(d),{})
        self.error('OFFER_EXPIRED',lambda:self.fleet.accept(d,r['id']))
    def test_legacy_and_fleet_offer_exclusion_both_directions(self):
        d=self.register()['driverId'];r=self.book();self.fleet.offer(d)
        self.service.driver_availability({'online':True})
        self.assertEqual(self.service.driver_offer(),{})
        self.fleet.action(d,r['id'],'decline',{})
        self.assertEqual(self.service.driver_offer()['id'],r['id'])
        self.assertEqual(self.fleet.offer(d),{})
    def test_suspension_blocks_offers_but_allows_active_trip_finish(self):
        d,r=self.assigned();self.fleet.approve(d,{'status':'SUSPENDED'})
        self.assertEqual(self.fleet.offer(d),{})
        self.fleet.location(d,{'latitude':49.28,'longitude':-123.12})
        self.fleet.action(d,r,'arrive',{});self.fleet.action(d,r,'start',{'pin':self.service.get('p',r)['pin']});self.fleet.action(d,r,'complete',{})
    def test_replacement_and_expiry_block_dispatch(self):
        d=self.register()['driverId'];self.fleet.submit_document(d,'LICENCE',self.document(2))
        self.assertFalse(self.fleet.status(d)['online'])
        self.error('DRIVER_NOT_APPROVED',lambda:self.fleet.availability(d,{'online':True}))
        self.fleet.review_document(d,'LICENCE',{'status':'APPROVED','revision':3})
        self.now+=366*86400000
        self.assertFalse(self.fleet.status(d)['documentsReady'])
    def test_active_ride_blocks_offline_upload_and_access_reset(self):
        d,r=self.assigned()
        for fn in (lambda:self.fleet.availability(d,{'online':False}),lambda:self.fleet.submit_document(d,'LICENCE',self.document(2)),lambda:self.fleet.rotate_token(d)):
            self.error('ACTIVE_RIDE',fn)
    def test_access_reset_revokes_old_token_and_persists_after_restart(self):
        reg=self.register();d=reg['driverId'];new=self.fleet.rotate_token(d)['developmentToken']
        self.error('FLEET_AUTH_REQUIRED',lambda:self.fleet.authenticate('Bearer '+reg['developmentToken']))
        service=Service(self.service.database,clock=lambda:self.now)
        self.assertEqual(service.fleet.authenticate('Bearer '+new),d)
        self.assertFalse(service.fleet.status(d)['online'])
        self.assertTrue(service.fleet.status(d)['documentsReady'])
    def test_profile_change_requires_review_and_cannot_unsuspend(self):
        d=self.register()['driverId']
        self.fleet.update_profile(d,{'name':'Updated name','vehicle':'New car','plate':'NEW'})
        status=self.fleet.status(d)
        self.assertEqual(status['status'],'PENDING');self.assertFalse(status['online'])
        self.error('DOCUMENTS_REQUIRED',lambda:self.fleet.approve(d,{'status':'APPROVED'}))
        self.assertTrue(all(x['status']=='PENDING' for x in self.fleet.documents(d)['documents']))
        self.fleet.approve(d,{'status':'SUSPENDED'})
        self.fleet.update_profile(d,{'name':'Updated again','vehicle':'New car','plate':'NEW'})
        self.assertEqual(self.fleet.status(d)['status'],'SUSPENDED')

    def test_active_trip_survives_server_restart(self):
        d,r=self.assigned()
        with self.service.connect() as db:
            ride=self.service.get('p',r,db)
            ride['driver'].pop('rating');ride['driver'].pop('colour');ride['driver']['pickupEtaMinutes']=None
            db.execute('UPDATE rides SET payload=? WHERE id=?',(json.dumps(ride),r))
        restarted=Service(self.service.database,clock=lambda:self.now)
        restored=restarted.fleet.active_ride(d)
        self.assertEqual(restored['id'],r)
        self.assertIsInstance(restored['driver']['pickupEtaMinutes'],int)
        self.assertIn('rating',restored['driver']);self.assertIn('colour',restored['driver'])
        self.error('ACTIVE_RIDE',lambda:restarted.fleet.update_profile(d,{'name':'Change','vehicle':'Car','plate':'P'}))

    def test_scheduled_ride_enters_fleet_only_when_due(self):
        d=self.register()['driverId']
        self.request.update(scheduled=True,scheduledAtEpochMs=self.now+3600000,scheduleTimeZone='UTC')
        ride=self.book()
        self.assertEqual(self.fleet.offer(d),{})
        self.now+=3600000
        self.service.activate_due()
        self.fleet.location(d,{'latitude':49.28,'longitude':-123.12})
        self.assertEqual(self.fleet.offer(d)['id'],ride['id'])

    def test_build28_document_schema_migrates_without_losing_rows(self):
        import sqlite3
        database=self.tmp.name+'/old-schema.sqlite'
        with closing(sqlite3.connect(database)) as db, db:
            db.execute("CREATE TABLE fleet_documents (driver_id TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'NOT_SUBMITTED', expiry_date TEXT, PRIMARY KEY(driver_id,kind))")
            db.execute("INSERT INTO fleet_documents VALUES ('legacy-driver','LICENCE','NOT_SUBMITTED',NULL)")
        migrated=Service(database,clock=lambda:self.now)
        docs=migrated.fleet.documents('legacy-driver')['documents']
        self.assertEqual(len(docs),1);self.assertEqual(docs[0]['kind'],'LICENCE');self.assertEqual(docs[0]['revision'],0)

    def test_http_android_contract_and_admin_access(self):
        with patch.dict(os.environ,{'RIDENOVA_DEV_ADMIN_TOKEN':'admin-test-only', 'RIDENOVA_OWNER_USERNAME':'', 'RIDENOVA_OWNER_PASSWORD':''}):
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.service));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def call(path,token=None,body=None):
                headers={'Content-Type':'application/json'}
                if token:headers['Authorization']='Bearer '+token
                req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,headers=headers,data=None if body is None else json.dumps(body).encode())
                with urllib.request.urlopen(req) as response:return json.load(response)
            try:
                r=call('/v2/fleet/register',body={'name':'HTTP Test','vehicle':'Car','plate':'HTTP','category':'ECONOMY'});token=r['developmentToken'];d=r['driverId'];admin='admin-test-only'
                with self.assertRaises(urllib.error.HTTPError) as e:call('/v2/fleet/admin/drivers',token)
                self.assertEqual(e.exception.code,403)
                for kind in KINDS:
                    body=self.document();body['contentBase64']=base64.b64encode(b'%PDF-1.4\n'+b'x'*40000).decode()
                    call('/v2/fleet/driver/documents/'+kind,token,body)
                    call('/v2/fleet/admin/drivers/'+d+'/documents/'+kind+'/review',admin,{'status':'APPROVED','revision':1})
                call('/v2/fleet/admin/drivers/'+d+'/status',admin,{'status':'APPROVED'})
                call('/v2/fleet/driver/availability',token,{'online':True})
                call('/v2/fleet/driver/location',token,{'latitude':49.28,'longitude':-123.12})
                ride=self.book();rid=ride['id'];self.assertEqual(call('/v2/fleet/driver/requests/current',token)['id'],rid)
                call('/v2/fleet/driver/rides/'+rid+'/accept',token,{})
                self.assertNotIn('pin',call('/v2/fleet/driver/rides/active',token))
                call('/v2/fleet/driver/rides/'+rid+'/arrive',token,{})
                call('/v2/fleet/driver/rides/'+rid+'/start',token,{'pin':self.service.get('p',rid)['pin']})
                call('/v2/fleet/driver/rides/'+rid+'/complete',token,{})
                self.assertEqual(len(call('/v2/fleet/driver/trips',token)['trips']),1)
                self.assertTrue(call('/v2/fleet/admin/drivers/'+d+'/audit',admin)['events'])
                with self.assertRaises(urllib.error.HTTPError) as e:call('/v2/fleet/driver/status','bad')
                self.assertEqual(e.exception.code,401)
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
