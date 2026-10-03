import copy
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from server import APIError, Service, make_handler


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1000000
        self.service = Service(self.temp.name + '/test.db', clock=lambda: self.now)
        self.owner = 'passenger-a'
        self.request = {'pickup': {'name': 'A', 'address': 'Vancouver', 'latitude': 49.28, 'longitude': -123.12},
                        'destination': {'name': 'B', 'address': 'Burnaby', 'latitude': 49.25, 'longitude': -122.98},
                        'scheduled': False, 'route': {'distanceKm': 0, 'durationMinutes': 0}}

    def tearDown(self):
        self.temp.cleanup()

    def booking(self, tier='ECONOMY'):
        quote = self.service.quote(self.owner, self.request)
        return {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': tier, 'fareCad': 0.01}, 'draft': {}}

    def error(self, code, fn):
        with self.assertRaises(APIError) as error:
            fn()
        self.assertEqual(error.exception.code, code)

    def test_server_fare_ignores_client_values(self):
        ride = self.service.create(self.owner, self.booking())
        self.assertGreater(ride['option']['fareCad'], 0.01)
        self.assertGreater(ride['draft']['routeEstimate']['distanceKm'], 0)

    def test_price_breakdown_balances(self):
        quote = self.service.quote(self.owner, self.request)
        for option in quote['options']:
            b = option['breakdown']
            self.assertEqual(b['totalCents'], b['subtotalCents'] + b['gstCents'])
            self.assertEqual(b['subtotalCents'], b['platformCommissionCents'] + b['driverGrossBeforeCostsCents'])

    def test_gst_inclusive_floor(self):
        self.service.config['tiers']['ECONOMY'].update(baseCents=0, perKmCents=0, perMinuteCents=0, minimumSubtotalCents=0)
        option = self.service.price('ECONOMY', {'distanceKm': 0, 'durationMinutes': 0})
        self.assertEqual(option['breakdown']['totalCents'], 443)
        self.assertEqual(option['breakdown']['gstCents'], 21)

    def test_quote_expiry_boundary(self):
        body = self.booking()
        self.now += 120000
        self.error('QUOTE_EXPIRED', lambda: self.service.create(self.owner, body))

    def test_duplicate_booking_concurrency(self):
        body = self.booking()
        with ThreadPoolExecutor(max_workers=6) as pool:
            rides = list(pool.map(lambda _: self.service.create(self.owner, body), range(12)))
        self.assertEqual(len({r['id'] for r in rides}), 1)
        self.assertEqual(len(self.service.list(self.owner)['rides']), 1)

    def test_replay_after_expiry(self):
        body = self.booking()
        ride = self.service.create(self.owner, body)
        self.now += 200000
        self.assertEqual(self.service.create(self.owner, body)['id'], ride['id'])

    def test_replay_different_tier(self):
        body = self.booking()
        self.service.create(self.owner, body)
        body['rideOption']['tier'] = 'XL'
        self.error('QUOTE_ALREADY_USED', lambda: self.service.create(self.owner, body))

    def test_one_active_ride(self):
        self.service.create(self.owner, self.booking())
        self.error('ACTIVE_RIDE_EXISTS', lambda: self.service.create(self.owner, self.booking()))

    def test_session_isolation(self):
        body = self.booking()
        self.error('QUOTE_NOT_FOUND', lambda: self.service.create('other', body))
        ride = self.service.create(self.owner, body)
        self.error('RIDE_NOT_FOUND', lambda: self.service.get('other', ride['id']))
        self.error('RIDE_NOT_FOUND', lambda: self.service.cancel('other', ride['id']))
        self.assertEqual(self.service.list('other')['rides'], [])

    def test_free_cancellation_at_boundary(self):
        ride = self.service.create(self.owner, self.booking())
        self.now += 120000
        self.assertEqual(self.service.cancel(self.owner, ride['id'])['cancellationFeeCad'], 0)

    def test_fee_after_boundary_and_idempotent_cancel(self):
        ride = self.service.create(self.owner, self.booking())
        self.now += 120001
        cancelled = self.service.cancel(self.owner, ride['id'])
        self.assertEqual(cancelled['cancellationFeeCad'], 5)
        self.assertEqual(self.service.cancel(self.owner, ride['id']), cancelled)
        with self.service.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 2)

    def test_invalid_transition_and_cancel_after_start(self):
        ride = self.service.create(self.owner, self.booking())
        self.error('INVALID_TRANSITION', lambda: self.service.transition(ride['id'], 'COMPLETED'))
        for status in ('DRIVER_ASSIGNED', 'DRIVER_ARRIVED', 'TRIP_STARTED'):
            self.service.transition(ride['id'], status)
        self.error('INVALID_TRANSITION', lambda: self.service.cancel(self.owner, ride['id']))

    def test_development_driver_position_requires_assignment_and_persists(self):
        ride = self.service.create(self.owner, self.booking())
        point = {'latitude': 49.28, 'longitude': -123.11}
        self.error('INVALID_TRANSITION', lambda: self.service.report_driver_position(ride['id'], point))
        self.service.transition(ride['id'], 'DRIVER_ASSIGNED')
        for invalid in ({'latitude': float('nan'), 'longitude': -123},
                        {'latitude': True, 'longitude': -123},
                        {'latitude': 100, 'longitude': -123},
                        {'latitude': '49.28', 'longitude': -123}):
            self.error('INVALID_POSITION', lambda: self.service.report_driver_position(ride['id'], invalid))
        updated = self.service.report_driver_position(ride['id'], point)
        self.assertEqual(updated['driverPosition'], {**point, 'recordedAtEpochMs': self.now})
        self.assertEqual(Service(self.service.database).get(self.owner, ride['id'])['driverPosition'], updated['driverPosition'])
        self.service.transition(ride['id'], 'DRIVER_ARRIVED')
        self.service.transition(ride['id'], 'TRIP_STARTED')
        self.service.transition(ride['id'], 'COMPLETED')
        self.error('INVALID_TRANSITION', lambda: self.service.report_driver_position(ride['id'], point))

    def test_persistence_after_restart(self):
        ride = self.service.create(self.owner, self.booking())
        reopened = Service(self.service.database)
        self.assertEqual(reopened.get(self.owner, ride['id']), ride)

    def test_reject_invalid_coordinates(self):
        for value in (float('nan'), float('inf'), True, '49', 91, None):
            request = copy.deepcopy(self.request)
            request['pickup']['latitude'] = value
            self.error('INVALID_COORDINATES', lambda: self.service.quote(self.owner, request))

    def test_out_of_area(self):
        self.request['pickup']['latitude'] = 50
        self.error('OUTSIDE_DEVELOPMENT_AREA', lambda: self.service.quote(self.owner, self.request))

    def test_schedule_requires_timestamp(self):
        self.request['scheduled'] = True
        self.error('INVALID_SCHEDULE', lambda: self.service.quote(self.owner, self.request))

    def test_http_contract(self):
        with patch.dict(os.environ, {'RIDENOVA_OWNER_USERNAME':'', 'RIDENOVA_OWNER_PASSWORD':''}):
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        access = [None]
        def call(path, body=None, session=True, authenticated=True, method=None):
            headers = {'Content-Type': 'application/json'}
            if session:
                headers['X-RideNova-Session'] = 'development-session-123456'
            if authenticated and access[0]:
                headers['Authorization'] = 'Bearer ' + access[0]
            req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers, method=method)
            with urllib.request.urlopen(req) as response:
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                return json.load(response)
        try:
            self.assertEqual(call('/health', session=False, authenticated=False)['version'], '42.1')
            with self.assertRaises(urllib.error.HTTPError) as error:
                call('/v1/passenger/rides', session=False)
            self.assertEqual(error.exception.code, 401)
            challenge = call('/v1/auth/request-otp', {'phone': '+1 604 555 0123'}, authenticated=False)
            session = call('/v1/auth/verify-otp', {'challengeId': challenge['challengeId'], 'code': challenge['developmentCode']}, authenticated=False)
            access[0] = session['accessToken']
            profile = call('/v1/passenger/me')
            self.assertEqual(profile['phone'], '+16045550123')
            profile = call('/v1/passenger/me', {'firstName': 'Test', 'lastName': 'Rider', 'email': ''}, method='PATCH')
            self.assertTrue(profile['profileComplete'])
            quote = call('/v1/passenger/quotes', self.request)
            ride = call('/v1/passenger/rides', {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'}})
            self.assertEqual(call('/v1/passenger/rides')['rides'][0]['id'], ride['id'])
            self.assertEqual(call('/v1/passenger/rides/' + ride['id'])['status'], 'SEARCHING')
            self.assertEqual(call('/v1/passenger/rides/' + ride['id'] + '/cancel', {})['status'], 'CANCELLED_BY_RIDER')
            with self.assertRaises(urllib.error.HTTPError) as error:
                call('/v1/admin/rides/' + ride['id'] + '/events')
            self.assertEqual(error.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
