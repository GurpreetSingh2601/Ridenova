"""Build 43 pickup snapshots and zero-fee no-show regression tests."""
import json
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor
import test_build29 as previous
from server import Service, make_handler, APIError
from fleet35 import FleetError


class Build43Tests(unittest.TestCase):
    setUp = previous.Build29Tests.setUp
    tearDown = previous.Build29Tests.tearDown
    document = previous.Build29Tests.document
    register = previous.Build29Tests.register
    book = previous.Build29Tests.book
    assigned = previous.Build29Tests.assigned
    error = previous.Build29Tests.error

    def ready(self):
        driver, ride = self.assigned()
        self.fleet.action(driver, ride, 'arrive', {})
        return driver, ride

    def elapsed(self, driver):
        self.now += 300_001
        self.fleet.location(driver, {'latitude': 49.28, 'longitude': -123.12})

    def cancel(self, driver, ride):
        return self.fleet.action(driver, ride, 'no-show', {'reason': 'RIDER_NOT_AT_PICKUP', 'confirmedPickupChecked': True})

    def test_pickup_notes_are_validated_and_bound_to_quote(self):
        self.request['pickupNotes'] = '  Main entrance\nBlue jacket  '
        quote = self.service.quote('p', self.request)
        ride = self.service.create('p', {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'}, 'draft': {'pickupNotes': 'tampered'}})
        self.assertEqual(ride['draft']['pickupNotes'], 'Main entrance\nBlue jacket')
        self.assertEqual(self.service.admin_overview()['rides'][0]['pickupNotes'], 'Main entrance\nBlue jacket')
        for value in ['x' * 281, {}, None, 'bad\x00note']:
            with self.subTest(value=value), self.assertRaises(APIError):
                self.service.quote('p', {**self.request, 'pickupNotes': value})

    def test_legacy_quote_has_empty_notes(self):
        self.assertEqual(self.book()['draft']['pickupNotes'], '')

    def test_wait_timer_is_server_authoritative_and_retry_does_not_restart(self):
        driver, ride = self.ready()
        initial = self.fleet.waiting(driver, ride)
        self.assertTrue(initial['verifiedArrival'])
        self.assertEqual(initial['remainingSeconds'], 300)
        self.error('WAIT_NOT_COMPLETE', lambda: self.cancel(driver, ride))
        self.now += 20_000
        self.fleet.action(driver, ride, 'arrive', {})
        self.assertEqual(self.fleet.waiting(driver, ride)['eligibleAtEpochMs'], initial['eligibleAtEpochMs'])
        self.assertEqual(self.fleet.waiting(driver, ride)['remainingSeconds'], 280)

    def test_no_show_requires_fresh_nearby_gps_and_explicit_confirmation(self):
        driver, ride = self.ready()
        self.now += 300_001
        self.error('WAIT_NOT_COMPLETE', lambda: self.cancel(driver, ride))
        self.fleet.location(driver, {'latitude': 49.4, 'longitude': -123.12})
        self.error('WAIT_NOT_COMPLETE', lambda: self.cancel(driver, ride))
        self.fleet.location(driver, {'latitude': 49.28, 'longitude': -123.12})
        for reason in [None, {}, [], True, 'OTHER']:
            with self.subTest(reason=reason):
                self.error('NO_SHOW_REASON_REQUIRED', lambda: self.fleet.action(driver, ride, 'no-show', {'reason': reason, 'confirmedPickupChecked': True}))
        self.error('PICKUP_CHECK_REQUIRED', lambda: self.fleet.action(driver, ride, 'no-show', {'reason': 'RIDER_NOT_AT_PICKUP'}))
        self.assertEqual(self.cancel(driver, ride)['status'], 'CANCELLED_NO_SHOW')

    def test_unverified_and_legacy_arrival_require_new_full_wait(self):
        driver, ride = self.assigned()
        self.fleet.location(driver, {'latitude': 49.4, 'longitude': -123.12})
        self.fleet.action(driver, ride, 'arrive', {})
        self.assertFalse(self.fleet.waiting(driver, ride)['verifiedArrival'])
        self.elapsed(driver)
        self.error('WAIT_NOT_COMPLETE', lambda: self.cancel(driver, ride))
        self.fleet.action(driver, ride, 'arrive', {})
        self.assertEqual(self.fleet.waiting(driver, ride)['remainingSeconds'], 300)
        with self.service.connect() as db:
            data = json.loads(db.execute('SELECT payload FROM rides WHERE id=?', (ride,)).fetchone()[0]); data.pop('waiting')
            db.execute('UPDATE rides SET payload=? WHERE id=?', (json.dumps(data), ride))
        self.fleet.action(driver, ride, 'arrive', {})
        self.assertEqual(self.fleet.waiting(driver, ride)['remainingSeconds'], 300)

    def test_retry_concurrency_and_restart_do_not_duplicate_cancellation_or_earnings(self):
        driver, ride = self.ready(); self.elapsed(driver)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: self.cancel(driver, ride), range(2)))
        self.assertTrue(all(r['status'] == 'CANCELLED_NO_SHOW' for r in results))
        reopened = Service(self.tmp.name + '/db.sqlite', clock=lambda: self.now)
        self.assertEqual(reopened.fleet.action(driver, ride, 'no-show', {})['status'], 'CANCELLED_NO_SHOW')
        snapshot = reopened.get('p', ride)
        self.assertEqual(snapshot['cancellationFeeCad'], 0)
        self.assertEqual(snapshot['payment']['amountCents'], 0)
        self.assertEqual(reopened.fleet.active_ride(driver), {})
        with reopened.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM development_earnings WHERE ride_id=?', (ride,)).fetchone()[0], 0)
            events = db.execute('SELECT type FROM events WHERE ride_id=?', (ride,)).fetchall()
            self.assertEqual([r[0] for r in events].count('FLEET_NO_SHOW'), 1)

    def test_owner_and_trip_stage_enforced(self):
        driver, ride = self.ready(); other = self.register()['driverId']
        self.error('FORBIDDEN', lambda: self.fleet.waiting(other, ride))
        self.error('FORBIDDEN', lambda: self.cancel(other, ride))
        self.elapsed(driver)
        self.fleet.action(driver, ride, 'start', {'pin': self.service.get('p', ride)['pin']})
        self.error('INVALID_TRANSITION', lambda: self.cancel(driver, ride))
        self.fleet.action(driver, ride, 'complete', {})
        self.error('INVALID_TRANSITION', lambda: self.cancel(driver, ride))

    def test_start_no_show_race_has_one_terminal_decision(self):
        driver, ride = self.ready(); self.elapsed(driver)
        pin = self.service.get('p', ride)['pin']
        def action(name):
            try:
                return self.fleet.action(driver, ride, name, {'pin': pin, 'reason': 'RIDER_NOT_AT_PICKUP', 'confirmedPickupChecked': True})['status']
            except FleetError: return 'REJECTED'
        with ThreadPoolExecutor(2) as pool: results = list(pool.map(action, ['start', 'no-show']))
        self.assertEqual(results.count('REJECTED'), 1)
        self.assertIn(self.service.get('p', ride)['status'], ['TRIP_STARTED', 'CANCELLED_NO_SHOW'])

    def test_waiting_endpoint_requires_driver_auth_and_handles_no_show(self):
        reg = self.register(); driver = reg['driverId']; ride = self.book()['id']
        self.fleet.offer(driver); self.fleet.accept(driver, ride); self.fleet.action(driver, ride, 'arrive', {})
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def call(action, body=None, token=None):
            req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/v2/fleet/driver/rides/{ride}/{action}',
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + token} if token else {})})
            with urllib.request.urlopen(req, timeout=5) as response: return json.load(response)
        try:
            with self.assertRaises(urllib.error.HTTPError) as error: call('waiting')
            self.assertEqual(error.exception.code, 401)
            self.assertEqual(call('waiting', token=reg['developmentToken'])['remainingSeconds'], 300)
            self.elapsed(driver)
            self.assertEqual(call('no-show', {'reason': 'RIDER_NOT_AT_PICKUP', 'confirmedPickupChecked': True}, reg['developmentToken'])['status'], 'CANCELLED_NO_SHOW')
        finally: server.shutdown(); server.server_close(); thread.join()

    def test_no_show_releases_driver_and_allows_new_booking(self):
        driver, ride = self.ready(); self.elapsed(driver); self.cancel(driver, ride)
        second = self.book()
        self.assertNotEqual(second['id'], ride)
        self.assertEqual(self.fleet.offer(driver)['id'], second['id'])
        self.assertEqual(self.service.get('p', ride)['status'], 'CANCELLED_NO_SHOW')

    def test_passenger_cancel_races_no_show_without_overwriting_result(self):
        driver, ride = self.ready(); self.elapsed(driver)
        def action(kind):
            try:
                return (self.cancel(driver, ride) if kind == 'driver' else self.service.cancel('p', ride))['status']
            except (FleetError, APIError): return 'REJECTED'
        with ThreadPoolExecutor(2) as pool: results = list(pool.map(action, ['driver', 'passenger']))
        self.assertEqual(results.count('REJECTED'), 1)
        snapshot = self.service.get('p', ride)
        self.assertIn(snapshot['status'], ['CANCELLED_NO_SHOW', 'CANCELLED_BY_RIDER'])
        if snapshot['status'] == 'CANCELLED_NO_SHOW': self.assertEqual(snapshot['cancellationFeeCad'], 0)

if __name__ == '__main__': unittest.main()
