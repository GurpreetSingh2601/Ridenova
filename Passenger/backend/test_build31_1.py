"""Regression scenarios for the reported old-driver/fleet contradiction and dispatch diagnosis."""
import json
import os
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import test_build29 as base
from server import make_handler

class Build311Tests(unittest.TestCase):
    setUp=base.Build29Tests.setUp
    tearDown=base.Build29Tests.tearDown
    register=base.Build29Tests.register
    document=base.Build29Tests.document
    book=base.Build29Tests.book

    def test_overview_uses_fleet_even_when_legacy_driver_offline(self):
        d=self.register()['driverId']
        data=self.service.admin_overview()
        self.assertFalse(data['driver']['online'])  # Old independent demo record stays separate.
        self.assertEqual(data['driverStatusSource'],'fleet')
        status=next(x for x in data['fleetDrivers'] if x['driverId']==d)
        self.assertEqual(status,self.fleet.list_drivers()['drivers'][0])
        self.assertTrue(status['online']);self.assertTrue(status['dispatchReady'])

    def test_started_trip_reports_its_actual_fleet_driver(self):
        d=self.register()['driverId'];ride=self.book();self.fleet.offer(d)
        self.fleet.accept(d,ride['id']);self.fleet.action(d,ride['id'],'arrive',{})
        with self.service.connect() as db: pin=json.loads(db.execute('SELECT payload FROM rides WHERE id=?',(ride['id'],)).fetchone()[0])['pin']
        self.fleet.action(d,ride['id'],'start',{'pin':pin})
        data=self.service.admin_overview();status=data['fleetDrivers'][0]
        self.assertTrue(status['online']);self.assertEqual(status['activeRideId'],ride['id'])
        self.assertEqual(status['activeRideStatus'],'TRIP_STARTED')
        self.assertEqual(status['dispatchReason'],'ACTIVE_TRIP');self.assertFalse(status['dispatchReady'])
        self.assertEqual(data['rides'][0]['driverId'],d)

    def test_online_without_fresh_gps_is_not_reported_ready(self):
        d=self.register()['driverId'];self.now+=30001
        status=self.fleet.status(d)
        self.assertTrue(status['online']);self.assertFalse(status['dispatchReady'])
        self.assertEqual(status['dispatchReason'],'LOCATION_STALE')
        self.book();self.assertEqual(self.fleet.offer(d),{})
        self.fleet.location(d,{'latitude':49.28,'longitude':-123.12})
        self.assertEqual(self.fleet.status(d)['dispatchReason'],'READY')
        self.assertTrue(self.fleet.offer(d))

    def test_missing_gps_and_offline_are_distinct(self):
        d=self.register()['driverId']
        with self.service.connect() as db: db.execute('UPDATE fleet_drivers SET located_ms=NULL WHERE id=?',(d,))
        self.assertEqual(self.fleet.status(d)['dispatchReason'],'LOCATION_REQUIRED')
        self.fleet.availability(d,{'online':False})
        self.assertEqual(self.fleet.status(d)['dispatchReason'],'OFFLINE')

    def test_economy_driver_does_not_receive_xl_request(self):
        d=self.register(category='ECONOMY')['driverId'];self.book(tier='XL')
        self.assertEqual(self.fleet.offer(d),{})
        self.assertEqual(self.fleet.status(d)['category'],'ECONOMY')
        self.assertIsNone(self.fleet.passenger_availability(self.request['pickup'],'XL'))

    def test_ui_and_background_poll_share_one_lease(self):
        d=self.register()['driverId'];ride=self.book()
        foreground=self.fleet.offer(d);background=self.fleet.offer(d)
        self.assertEqual(foreground,background)
        self.assertEqual(foreground['id'],ride['id'])
        with self.service.connect() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM fleet_offers').fetchone()[0],1)
        self.fleet.accept(d,ride['id']);self.assertEqual(self.fleet.offer(d),{})

    def test_renewed_offer_has_new_deadline_for_same_ride(self):
        d=self.register()['driverId'];self.book();first=self.fleet.offer(d)
        self.now+=20001
        self.assertEqual(self.fleet.offer(d),{})
        self.now+=20001;self.fleet.location(d,{'latitude':49.28,'longitude':-123.12})
        second=self.fleet.offer(d)
        self.assertEqual(first['id'],second['id']);self.assertGreater(second['expiresAtEpochMs'],first['expiresAtEpochMs'])

    def test_http_driver_poll_and_admin_share_status_after_booking(self):
        reg=self.register();d=reg['driverId'];ride=self.book()
        with patch.dict(os.environ,{'RIDENOVA_DEV_ADMIN_TOKEN':'test-admin-311', 'RIDENOVA_OWNER_USERNAME':'', 'RIDENOVA_OWNER_PASSWORD':''}):
            http=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.service))
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            def get(path,token):
                request=urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+path,headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(request) as response: return json.load(response)
            try:
                status=get('/v2/fleet/driver/status',reg['developmentToken'])
                offer=get('/v2/fleet/driver/requests/current',reg['developmentToken'])
                admin=get('/v1/admin/overview','test-admin-311')
                self.assertEqual(status['driverId'],d);self.assertTrue(status['dispatchReady'])
                self.assertEqual(offer['id'],ride['id'])
                for key in ('pickup','destination','riderName','expiresAtEpochMs','driverEstimatedEarningsCad'): self.assertIn(key,offer)
                self.assertEqual(admin['fleetDrivers'][0]['online'],status['online'])
                self.assertNotIn('developmentToken',str(admin));self.assertNotIn('password_hash',str(admin))
            finally: http.shutdown();thread.join();http.server_close()

if __name__=='__main__': unittest.main()
