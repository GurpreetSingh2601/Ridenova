"""Build 45 regression scenarios: routing inputs, cents, assignment boundaries and caps."""
import json
import os
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
import test_build29 as previous
from staff38 import Staff
from server import Service
from compensation45 import bounds, period_at
from fleet28 import FleetError

class Build45Tests(unittest.TestCase):
    setUp=previous.Build29Tests.setUp
    tearDown=previous.Build29Tests.tearDown
    register=previous.Build29Tests.register
    document=previous.Build29Tests.document
    book=previous.Build29Tests.book
    assigned=previous.Build29Tests.assigned
    error=previous.Build29Tests.error

    def road(self,meters=37000,seconds=2280):
        self.service.pickup_routes.provider=lambda a,b:dict(distanceMeters=meters,durationSeconds=seconds,encodedPolyline='_p~iF~ps|U_ulLnnqC_mqNvxq`@')
        self.service.pickup_routes.cache.clear()

    def close(self,d,r,minutes=70):
        self.fleet.action(d,r,'arrive',{})
        self.fleet.action(d,r,'start',{'pin':self.service.get('p',r)['pin']})
        self.now+=minutes*60000
        self.fleet.action(d,r,'complete',{})

    def review(self,report,meters=69200):
        Staff(self.service.database)
        self.service.compensation.review('owner',dict(engagementId=report['entries'][0]['id'],verifiedMeters=meters,reason='Verified test odometer evidence'))

    def test_bc_place_road_snapshot_and_pay_math(self):
        self.road();d=self.register()['driverId'];r=self.book()
        with self.service.connect() as db:
            ride=json.loads(db.execute('SELECT payload FROM rides WHERE id=?',(r['id'],)).fetchone()[0])
            ride['draft']['routeEstimate'].update(distanceKm=32.2,durationMinutes=32)
            ride['option']['breakdown']['driverGrossBeforeCostsCents']=3583
            db.execute('UPDATE rides SET payload=? WHERE id=?',(json.dumps(ride),r['id']))
        offer=self.fleet.offer(d);c=offer['compensation']
        self.assertEqual((offer['pickupDistanceKm'],offer['pickupEtaMin']),(37,38))
        self.assertEqual((c['engagedMeters'],c['engagedSeconds']),(69200,4200))
        self.assertEqual((c['distanceAllowanceCents'],c['estimatedTotalCents'],c['earningsPerHourCents']),(3114,6697,3071))
        self.assertEqual(c['minimumWageEquivalentCents'],2554)
        self.assertEqual(self.fleet.offer(d),offer)
        self.fleet.accept(d,r['id']);saved=self.service.get('p',r['id'])
        self.assertEqual(saved['driver']['pickupEtaMinutes'],38)
        self.assertEqual(saved['dispatch']['pickupDistanceKm'],37)
        self.assertNotIn('offer45',saved)

    def test_route_failure_is_labelled_and_staging_fails_closed(self):
        self.service.pickup_routes.provider=lambda a,b:(_ for _ in ()).throw(TimeoutError())
        d=self.register()['driverId'];r=self.book();offer=self.fleet.offer(d)
        self.assertEqual(offer['pickupRoute']['source'],'STRAIGHT_LINE_FALLBACK')
        self.service.settings=type('Settings',(),{'environment':'staging'})()
        self.error('PICKUP_UNAVAILABLE',lambda:self.fleet.accept(d,r['id']))

    def test_pickup_limits_exclude_road_detour(self):
        self.road(51000,1200);d=self.register()['driverId'];self.book()
        self.assertEqual(self.fleet.offer(d),{})
        self.assertIsNone(self.fleet.passenger_availability(self.request['pickup'],'ECONOMY'))

    def test_route_cache_reuses_then_refreshes(self):
        self.road();calls=[]
        self.service.pickup_routes.provider=lambda a,b:(calls.append(a) or dict(distanceMeters=37000,durationSeconds=2280,encodedPolyline='abc'))
        route=self.service.pickup_routes;p=self.request['pickup'];q=self.request['destination']
        self.assertEqual(route.get('d',p,q),route.get('d',p,q));self.assertEqual(len(calls),1)
        self.now+=31000;route.get('d',p,q);self.assertEqual(len(calls),2)

    def test_gps_duplicate_gap_and_legacy_reading_never_finalize_silently(self):
        d,r=self.assigned();self.now+=10000
        point=dict(latitude=49.2801,longitude=-123.12,accuracyMeters=5,observedAtEpochMs=self.now)
        self.fleet.location(d,point);self.fleet.location(d,point)
        report=self.service.compensation.report(d);self.assertLess(report['meters'],20)
        self.close(d,r);report=self.service.compensation.report(d)
        self.assertTrue(report['reviewRequired']);self.assertIn('FINAL_GPS_GAP',report['entries'][0]['issues'])

    def test_cancel_keeps_engaged_time_and_zero_base(self):
        d,r=self.assigned();self.now+=10*60000;self.service.cancel('p',r)
        report=self.service.compensation.report(d)
        self.assertEqual(report['engagedMs'],600000);self.assertEqual(report['baseEarningsCents'],0)
        self.assertEqual(report['topUpCents'],365)
        self.service.cancel('p',r);self.assertEqual(len(self.service.compensation.report(d)['entries']),1)

    def test_reassignment_closes_old_assignment(self):
        d,r=self.assigned();Staff(self.service.database);self.now+=60000
        self.service.operations44.reassign('owner',r,dict(expectedDriverId=d,reason='Driver unable to continue'))
        report=self.service.compensation.report(d)
        self.assertFalse(report['entries'][0]['active']);self.assertEqual(report['engagedMs'],60000)
        new=self.register()['driverId'];self.fleet.offer(new);self.fleet.accept(new,r)
        self.assertEqual(len(self.service.compensation.report(new)['entries']),1)
        self.assertEqual(self.service.compensation.report(d)['engagedMs'],60000)

    def test_period_reconciliation_is_idempotent_and_review_gated(self):
        d,r=self.assigned();self.close(d,r)
        report=self.service.compensation.report(d);period=report['period']
        self.error('PERIOD_NOT_READY',lambda:self.service.compensation.finalize('owner',d,period))
        self.review(report);self.now=bounds(period)[1]+1000
        one=self.service.compensation.finalize('owner',d,period)
        two=self.service.compensation.finalize('owner',d,period)
        self.assertEqual(one,two);self.assertEqual(one['distanceAllowanceCents'],3114)
        with self.service.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM finance_entries WHERE kind='DISTANCE_ALLOWANCE'").fetchone()[0],1)
        self.error('PERIOD_FINALIZED',lambda:self.review(report,70000))
        restarted=Service(self.service.database,clock=lambda:self.now)
        self.assertEqual(restarted.compensation.report(d,period)['finalized'],one)

    def test_pay_period_crossing_conserves_time_and_money(self):
        self.now=int(datetime(2026,9,15,23,50,tzinfo=ZoneInfo('America/Vancouver')).timestamp()*1000)
        d,r=self.assigned();self.close(d,r,20)
        a=self.service.compensation.report(d,'2026-09-01');b=self.service.compensation.report(d,'2026-09-16')
        self.assertEqual(a['engagedMs'],600000);self.assertEqual(b['engagedMs'],600000)
        self.assertTrue(a['entries'][0]['boundaryAllocation']);self.assertTrue(a['reviewRequired'])
        base=self.service.get('p',r)['option']['breakdown']['driverGrossBeforeCostsCents']
        self.assertEqual(a['baseEarningsCents']+b['baseEarningsCents'],base)

    def zone(self,budget=200):
        z=self.service.finance.create_zone(dict(label='Test zone',latitude=49.28,longitude=-123.12,radiusKm=2,category='ECONOMY',startMs=self.now-1000,endMs=self.now+3600000,bonusCents=200,budgetCents=budget))
        self.service.finance.toggle_zone(z['id'],True);return z['id']

    def test_bonus_reserves_at_acceptance_and_survives_expiry(self):
        z=self.zone();d,r=self.assigned()
        with self.service.connect() as db:self.assertEqual(db.execute('SELECT awarded_cents FROM boost_zones WHERE id=?',(z,)).fetchone()[0],200)
        self.close(d,r,70);self.fleet.action(d,r,'complete',{})
        self.assertEqual(self.service.compensation.report(d)['bonusCents'],200)
        with self.service.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM boost_awards').fetchone()[0],1)

    def test_cancel_releases_reserved_budget(self):
        z=self.zone();d,r=self.assigned();self.service.cancel('p',r)
        with self.service.connect() as db:
            self.assertEqual(db.execute('SELECT awarded_cents FROM boost_zones WHERE id=?',(z,)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM boost_awards').fetchone()[0],0)

    def test_overlapping_zones_only_highest_single_bonus(self):
        self.zone();self.zone();d=self.register()['driverId'];self.book()
        self.assertEqual(self.fleet.offer(d)['compensation']['bonusCents'],200)

    def test_future_policy_validation(self):
        Staff(self.service.database)
        self.error('INVALID_POLICY',lambda:self.service.compensation.policy('owner',dict(effectiveDate='2026-06-01',hourlyCents=2200,kmCents=45,reason='Too late')))
        result=self.service.compensation.policy('owner',dict(effectiveDate='2027-06-01',hourlyCents=2300,kmCents=46,reason='Test future policy'))
        self.assertEqual(result['policies'][-1]['hourlyCents'],2300)

    def test_period_dates_are_local_and_validate(self):
        self.assertEqual(period_at(bounds('2026-11-01')[0]),'2026-11-01')
        # Vancouver stays at UTC-7 after March 2026 (tzdata 2026.2+).
        self.assertEqual(bounds('2026-11-01')[1]-bounds('2026-11-01')[0],15*24*3600000)
        # Retain coverage of a historical fall-back transition.
        self.assertEqual(bounds('2025-11-01')[1]-bounds('2025-11-01')[0],(15*24+1)*3600000)
        self.error('INVALID_PERIOD',lambda:bounds('2026-09-02'))

    def test_http_compensation_rbac_and_driver_isolation(self):
        import threading, urllib.request, urllib.error
        from http.server import ThreadingHTTPServer
        from server import make_handler
        driver=self.register();other=self.register();self.book();self.fleet.offer(driver['driverId']);
        staff=Staff(self.service.database);tokens={}
        with staff.connect() as db:
            for role in ('OWNER','FINANCE','SUPPORT'):staff._create(db,role.lower(),'long-test-password-only',role,'bootstrap')
        for role in ('OWNER','FINANCE','SUPPORT'):tokens[role]=staff.login(dict(username=role.lower(),password='long-test-password-only'))['accessToken']
        tokens['DRIVER']=driver['developmentToken'];tokens['OTHER']=other['developmentToken']
        http=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.service));thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        def call(path,role,body=None):
            request=urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+path,data=json.dumps(body).encode() if body is not None else None,
                headers={'Authorization':'Bearer '+tokens.get(role,'invalid'),'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(request) as response:return response.status,json.load(response)
            except urllib.error.HTTPError as response:return response.code,json.load(response)
        try:
            self.assertEqual(call('/v4/trips/admin/earnings','NONE')[0],401)
            self.assertEqual(call('/v4/trips/admin/earnings','SUPPORT')[0],403)
            self.assertEqual(call('/v4/trips/admin/earnings','FINANCE')[0],200)
            self.assertEqual(call('/v4/trips/admin/review','FINANCE',{})[0],403)
            self.assertEqual(call('/v4/trips/admin/review','OWNER',{})[0],400)
            self.assertEqual(call('/v4/trips/driver/zones','NONE')[0],401)
            self.assertEqual(call('/v4/trips/driver/zones','DRIVER')[0],200)
            self.assertEqual(call('/v4/trips/driver/earnings?driverId='+driver['driverId'],'OTHER')[1]['entries'],[])
        finally:http.shutdown();http.server_close();thread.join()

    def test_two_drivers_cannot_reserve_last_bonus(self):
        self.zone();a=self.register()['driverId']
        first=self.book();self.fleet.offer(a)
        b=self.register()['driverId']
        # Freeze a second exclusive offer before the first reservation is taken.
        second=self.book(owner='other')
        offer=self.fleet.offer(b);self.assertEqual(offer['compensation']['bonusCents'],200)
        self.fleet.accept(a,first['id'])
        self.error('BOOST_CHANGED',lambda:self.fleet.accept(b,second['id']))
        self.assertEqual(self.service.get('other',second['id'])['status'],'SEARCHING')
        with self.service.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM engagements45').fetchone()[0],1)

    def test_no_show_time_still_counts_for_period_floor(self):
        d,r=self.assigned();self.fleet.action(d,r,'arrive',{})
        self.now+=301000
        self.fleet.location(d,dict(latitude=49.28,longitude=-123.12))
        self.fleet.action(d,r,'no-show',dict(reason='RIDER_NOT_AT_PICKUP',confirmedPickupChecked=True))
        report=self.service.compensation.report(d)
        self.assertGreater(report['engagedMs'],300000);self.assertGreater(report['topUpCents'],0)
        self.assertEqual(report['baseEarningsCents'],0)

    def test_additive_upgrade_preserves_old_rides(self):
        if self.service.postgres:self.skipTest('SQLite upgrade test; PostgreSQL migrations checked by integration harness')
        d,r=self.assigned()
        with self.service.connect() as db:
            original=db.execute('SELECT payload FROM rides WHERE id=?',(r,)).fetchone()[0]
            for table in ('engagements45','pay_periods45','pay_policy45','boost_reservations45','offer_snapshots45'):db.execute('DROP TABLE '+table)
        upgraded=Service(self.service.database,clock=lambda:self.now)
        with upgraded.connect() as db:
            self.assertEqual(db.execute('SELECT payload FROM rides WHERE id=?',(r,)).fetchone()[0],original)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
