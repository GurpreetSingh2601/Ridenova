"""End-to-end development driver / authenticated passenger contract tests."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from server import Service, make_handler


class DriverIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = Service(self.tmp.name + '/rides.db', clock=lambda: 1700000000000)
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.env = patch.dict(os.environ, {'RIDENOVA_DEV_DRIVER_TOKEN': 'separate-driver-secret',
                                            'RIDENOVA_DEV_ADMIN_TOKEN': 'separate-admin-secret'})
        self.env.start()
        self.passenger = None

    def tearDown(self):
        self.env.stop()
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def call(self, path, body=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(f'http://127.0.0.1:{self.http.server_port}{path}',
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    def driver(self, path, body=None):
        return self.call('/v1/driver/' + path, body, 'separate-driver-secret')

    def book(self):
        if not self.passenger:
            challenge = self.call('/v1/auth/request-otp', {'phone': '6045550123'})
            self.passenger = self.call('/v1/auth/verify-otp', {
                'challengeId': challenge['challengeId'], 'code': '246810'})['accessToken']
        quote = self.call('/v1/passenger/quotes', {
            'pickup': {'name': 'Pickup', 'address': 'Vancouver', 'latitude': 49.28, 'longitude': -123.12},
            'destination': {'name': 'Destination', 'address': 'Burnaby', 'latitude': 49.25, 'longitude': -122.98},
            'scheduled': False}, self.passenger)
        return self.call('/v1/passenger/rides', {'quoteToken': quote['quoteToken'],
            'rideOption': {'tier': 'ECONOMY'}}, self.passenger)

    def test_complete_ride_and_passenger_polling(self):
        ride = self.book()
        self.assertEqual(self.driver('requests/current'), {})
        self.driver('availability', {'online': True, 'name': 'A Driver', 'vehicle': 'Honda', 'plate': 'ABC123'})
        self.driver('location', {'latitude': 49.281, 'longitude': -123.121})
        offer = self.driver('requests/current')
        self.assertEqual(offer['id'], ride['id'])
        self.assertGreater(offer['fareCad'], 0)
        self.assertGreater(offer['pickupDistanceKm'], 0)
        self.assertLess(offer['pickupDistanceKm'], 1)
        self.assertEqual(self.driver('requests/current')['expiresAtEpochMs'], offer['expiresAtEpochMs'])
        self.assertEqual(self.driver('rides/' + ride['id'] + '/accept', {})['status'], 'DRIVER_ASSIGNED')
        self.assertEqual(self.driver('requests/current'), {})
        self.assertNotIn('pin', self.driver('rides/active'))
        passenger_ride = self.call('/v1/passenger/rides/' + ride['id'], token=self.passenger)
        self.assertEqual(passenger_ride['driver']['name'], 'A Driver')
        pin = passenger_ride['pin']
        self.assertEqual(self.driver('rides/' + ride['id'] + '/location',
            {'latitude': 49.27, 'longitude': -123.11})['driverPosition']['latitude'], 49.27)
        self.assertEqual(self.call('/v1/passenger/rides/' + ride['id'], token=self.passenger)
            ['driverPosition']['longitude'], -123.11)
        self.assertEqual(self.driver('rides/' + ride['id'] + '/arrive', {})['status'], 'DRIVER_ARRIVED')
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.driver('rides/' + ride['id'] + '/start', {'pin': '0000' if pin != '0000' else '1111'})
        self.assertEqual(error.exception.code, 403)
        self.assertEqual(self.driver('rides/' + ride['id'] + '/start', {'pin': pin})['status'], 'TRIP_STARTED')
        result = self.driver('rides/' + ride['id'] + '/complete', {})
        self.assertEqual(result['payment']['status'], 'CAPTURED_DEMO')
        history = self.driver('trips')
        self.assertEqual(history['trips'][0]['id'], ride['id'])
        self.assertGreater(history['trips'][0]['driverEarningsCad'], 0)
        self.assertEqual(result['payment']['amountCents'], ride['option']['breakdown']['totalCents'])
        self.assertEqual(self.call('/v1/passenger/rides/' + ride['id'], token=self.passenger)['status'], 'COMPLETED')
        self.assertEqual(self.driver('rides/active'), {})

    def test_replayed_driver_mutations_do_not_duplicate_events_or_earnings(self):
        ride = self.book()
        self.driver('availability', {'online': True, 'name': 'A Driver', 'vehicle': 'Honda', 'plate': 'ABC123'})
        self.driver('location', {'latitude': 49.281, 'longitude': -123.121})
        self.driver('requests/current')
        path = 'rides/' + ride['id'] + '/'
        self.assertEqual(self.driver(path + 'accept', {})['status'], 'DRIVER_ASSIGNED')
        self.assertEqual(self.driver(path + 'accept', {})['status'], 'DRIVER_ASSIGNED')
        pin = self.call('/v1/passenger/rides/' + ride['id'], token=self.passenger)['pin']
        self.assertEqual(self.driver(path + 'arrive', {})['status'], 'DRIVER_ARRIVED')
        self.assertEqual(self.driver(path + 'arrive', {})['status'], 'DRIVER_ARRIVED')
        self.assertEqual(self.driver(path + 'start', {'pin': pin})['status'], 'TRIP_STARTED')
        self.assertEqual(self.driver(path + 'start', {'pin': pin})['status'], 'TRIP_STARTED')
        self.assertEqual(self.driver(path + 'complete', {})['status'], 'COMPLETED')
        self.assertEqual(self.driver(path + 'complete', {})['status'], 'COMPLETED')
        with self.service.connect() as db:
            events = db.execute('SELECT type FROM events WHERE ride_id=?', (ride['id'],)).fetchall()
            earning_count = db.execute('SELECT COUNT(*) FROM development_earnings WHERE ride_id=?', (ride['id'],)).fetchone()[0]
        for event in ('DRIVER_ACCEPT', 'DRIVER_ARRIVE', 'DRIVER_START', 'DRIVER_COMPLETE'):
            self.assertEqual(sum(row[0] == event for row in events), 1, event)
        self.assertEqual(earning_count, 1)

    def test_decline_cancel_and_auth_separation(self):
        ride = self.book()
        for token in (None, 'separate-admin-secret', self.passenger):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.call('/v1/driver/rides/active', token=token)
            self.assertEqual(error.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.call('/v1/passenger/rides/' + ride['id'], token='separate-driver-secret')
        self.assertEqual(error.exception.code, 401)
        self.driver('availability', {'online': True, 'name': 'Driver', 'vehicle': 'Car', 'plate': 'PLATE'})
        self.driver('rides/' + ride['id'] + '/decline', {})
        self.assertEqual(self.driver('requests/current'), {})
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.driver('rides/' + ride['id'] + '/accept', {})
        self.assertEqual(error.exception.code, 409)
        self.service.clock = lambda: 1700000060001
        self.assertEqual(self.driver('requests/current')['id'], ride['id'])
        self.driver('rides/' + ride['id'] + '/accept', {})
        self.assertEqual(self.driver('rides/' + ride['id'] + '/cancel', {})['status'], 'SEARCHING')
        self.assertEqual(self.driver('rides/active'), {})
        self.assertEqual(self.call('/v1/passenger/rides/' + ride['id'], token=self.passenger)['status'], 'SEARCHING')

    def test_offer_expiry_requires_a_fresh_offer(self):
        ride = self.book()
        self.driver('availability', {'online': True, 'name': 'Driver', 'vehicle': 'Car', 'plate': 'PLATE'})
        first = self.driver('requests/current')
        self.assertEqual(first['expiresAtEpochMs'], 1700000020000)
        self.service.clock = lambda: 1700000020001
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.driver('rides/' + ride['id'] + '/accept', {})
        self.assertEqual(error.exception.code, 409)
        self.assertEqual(self.driver('requests/current'), {})
        self.service.clock = lambda: 1700000060002
        fresh = self.driver('requests/current')
        self.assertEqual(fresh['id'], ride['id'])
        self.assertGreater(fresh['expiresAtEpochMs'], first['expiresAtEpochMs'])

    def test_passenger_availability_uses_fresh_driver_location(self):
        self.book()  # establishes authenticated passenger session
        pickup = {'name': 'Pickup', 'address': 'Vancouver', 'latitude': 49.28, 'longitude': -123.12}
        offline = self.call('/v1/passenger/availability', {'pickup': pickup, 'tier': 'XL'}, self.passenger)
        self.assertFalse(offline['available'])

        self.driver('availability', {'online': True, 'name': 'Driver', 'vehicle': 'Car', 'plate': 'PLATE'})
        self.driver('location', {'latitude': 49.28005, 'longitude': -123.12005})
        nearby = self.call('/v1/passenger/availability', {'pickup': pickup, 'tier': 'XL'}, self.passenger)
        self.assertTrue(nearby['available'])
        self.assertEqual(nearby['etaMinutes'], 1)
        self.assertLessEqual(nearby['distanceKm'], 0.2)

        self.service.clock = lambda: 1700000030001
        stale = self.call('/v1/passenger/availability', {'pickup': pickup, 'tier': 'XL'}, self.passenger)
        self.assertFalse(stale['available'])
        self.assertGreaterEqual(stale['locationAgeSeconds'], 30)

    def test_build23_status_and_presence_updates_active_ride(self):
        ride = self.book()
        self.driver('availability', {'online': True, 'name': 'A Driver', 'vehicle': 'Honda', 'plate': 'ABC123'})
        status = self.driver('status')
        self.assertTrue(status['online'])
        self.assertEqual(status['name'], 'A Driver')
        self.driver('location', {'latitude': 49.281, 'longitude': -123.121})
        self.driver('requests/current')
        self.driver('rides/' + ride['id'] + '/accept', {})
        live = self.driver('location', {'latitude': 49.28002, 'longitude': -123.12002})
        self.assertEqual(live['activeRideId'], ride['id'])
        self.assertEqual(live['rideStatus'], 'DRIVER_ASSIGNED')
        passenger_ride = self.call('/v1/passenger/rides/' + ride['id'], token=self.passenger)
        self.assertAlmostEqual(passenger_ride['driverPosition']['latitude'], 49.28002, places=5)
        self.assertEqual(passenger_ride['driver']['pickupEtaMinutes'], 1)
        status = self.driver('status')
        self.assertEqual(status['activeRideId'], ride['id'])
        self.assertEqual(status['activeRideStatus'], 'DRIVER_ASSIGNED')

    def test_build23_presence_adds_live_trip_progress(self):
        ride = self.book()
        self.driver('availability', {'online': True, 'name': 'A Driver', 'vehicle': 'Honda', 'plate': 'ABC123'})
        self.driver('location', {'latitude': 49.281, 'longitude': -123.121})
        self.driver('requests/current')
        self.driver('rides/' + ride['id'] + '/accept', {})
        passenger_ride = self.call('/v1/passenger/rides/' + ride['id'], token=self.passenger)
        pin = passenger_ride['pin']
        self.driver('rides/' + ride['id'] + '/arrive', {})
        self.driver('rides/' + ride['id'] + '/start', {'pin': pin})
        live = self.driver('location', {'latitude': 49.255, 'longitude': -122.99})
        self.assertEqual(live['rideStatus'], 'TRIP_STARTED')
        passenger_ride = self.call('/v1/passenger/rides/' + ride['id'], token=self.passenger)
        self.assertIn('liveTrip', passenger_ride)
        self.assertGreaterEqual(passenger_ride['liveTrip']['progress'], 0.0)
        self.assertLessEqual(passenger_ride['liveTrip']['progress'], 1.0)
        self.assertGreater(passenger_ride['liveTrip']['remainingEtaMinutes'], 0)


if __name__ == '__main__':
    unittest.main()
