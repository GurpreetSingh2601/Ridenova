import base64
import http.client
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from server import Service, make_handler


class Build40ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1_800_000_000_000
        self.service = Service(self.temp.name + '/build40.sqlite3', clock=lambda: self.now)
        self.request = {
            'pickup': {'name': 'Pickup', 'address': '100 W Georgia St, Vancouver, BC',
                       'latitude': 49.2819, 'longitude': -123.1187},
            'destination': {'name': 'Destination', 'address': 'Metrotown, Burnaby, BC',
                            'latitude': 49.2269, 'longitude': -123.0076},
            'scheduled': False,
        }

    def tearDown(self):
        self.temp.cleanup()

    def selected_route(self):
        points = [
            {'latitude': 49.2819, 'longitude': -123.1187},
            {'latitude': 49.2630, 'longitude': -123.0690},
            {'latitude': 49.2269, 'longitude': -123.0076},
        ]
        geometry = sum(self.service.distance_km(a['latitude'], a['longitude'], b['latitude'], b['longitude'])
                       for a, b in zip(points, points[1:]))
        return {'distanceKm': round(geometry, 3), 'durationMinutes': 24,
                'routeType': 'BEST', 'isApproximate': False, 'path': points}

    def test_selected_google_route_is_the_authoritative_quote_and_booking_route(self):
        request = {**self.request, 'route': self.selected_route()}
        quote = self.service.quote('passenger', request)
        self.assertFalse(quote['routeChanged'])
        self.assertEqual(quote['route']['routeSource'], 'SELECTED_GOOGLE_ROUTE')
        self.assertEqual(quote['route']['distanceKm'], request['route']['distanceKm'])
        self.assertEqual(quote['route']['durationMinutes'], 24)
        ride = self.service.create('passenger', {
            'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'}})
        self.assertEqual(ride['draft']['routeEstimate'], quote['route'])
        self.assertEqual(ride['option']['breakdown']['totalCents'],
                         ride['option']['breakdown']['subtotalCents'] + ride['option']['breakdown']['gstCents'])

    def test_unverifiable_client_route_is_replaced_and_disclosed(self):
        request = {**self.request, 'route': {'distanceKm': 0.1, 'durationMinutes': 1,
                                             'routeType': 'BEST', 'isApproximate': False,
                                             'path': [self.request['pickup'], self.request['destination']]}}
        quote = self.service.quote('passenger', request)
        self.assertTrue(quote['routeChanged'])
        self.assertIn('review', quote['routeChangeReason'].lower())
        self.assertNotEqual(quote['route']['distanceKm'], 0.1)

    def test_large_road_route_quotes_and_compact_confirmation_over_http(self):
        route = self.selected_route()
        # Dense geometry reproduces the real road-route body size, not a tiny mock.
        start, middle, end = route['path']
        points = []
        for a, b in ((start, middle), (middle, end)):
            for i in range(1000):
                points.append({key: a[key] + (b[key] - a[key]) * i / 1000
                               for key in ('latitude', 'longitude')})
        route['path'] = points + [end]
        request = {**self.request, 'route': route}
        self.assertGreater(len(json.dumps(request).encode()), 32768)
        with patch.dict(os.environ, {'RIDENOVA_OWNER_USERNAME': '', 'RIDENOVA_OWNER_PASSWORD': ''}):
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        token = None

        def call(path, body=None):
            headers = {'Content-Type': 'application/json'}
            if token:
                headers['Authorization'] = 'Bearer ' + token
            req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + path,
                                         data=None if body is None else json.dumps(body).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)
        try:
            challenge = call('/v1/auth/request-otp', {'phone': '+16045550123'})
            token = call('/v1/auth/verify-otp', {'challengeId': challenge['challengeId'],
                         'code': challenge['developmentCode']})['accessToken']
            quote = call('/v1/passenger/quotes', request)
            self.assertFalse(quote['routeChanged'])
            self.assertIsNone(quote['routeChangeReason'])
            compact = {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'}}
            self.assertLess(len(json.dumps(compact).encode()), 1024)
            # The server rejects an oversized Content-Length BEFORE reading the
            # body. Sending that body concurrently with the early close can make
            # Windows report WSAECONNABORTED instead of exposing the HTTP 413.
            # Send headers only to test the early rejection deterministically.
            # The positive quote above still uploads the entire large polyline.
            oversized = json.dumps({**compact, 'draft': {'routeEstimate': route}}).encode()
            self.assertGreater(len(oversized), 32768)
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            try:
                connection.putrequest('POST', '/v1/passenger/rides')
                connection.putheader('Authorization', 'Bearer ' + token)
                connection.putheader('Content-Type', 'application/json')
                connection.putheader('Content-Length', str(len(oversized)))
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, 413)
                self.assertEqual(json.loads(response.read())['code'], 'BODY_TOO_LARGE')
            finally:
                connection.close()
            self.assertEqual(call('/v1/passenger/rides')['rides'], [])
            ride = call('/v1/passenger/rides', compact)
            self.assertEqual(ride['draft']['routeEstimate'], quote['route'])
            self.assertEqual(ride['option'], quote['options'][0])
            self.assertEqual(call('/v1/passenger/rides', compact)['id'], ride['id'])
            self.assertEqual(len(call('/v1/passenger/rides')['rides']), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def _ready_driver(self, suffix, latitude):
        fleet = self.service.fleet
        registered = fleet.register({'name': 'Driver ' + suffix, 'vehicle': 'Test car',
                                     'plate': 'B40' + suffix, 'category': 'ECONOMY'})
        driver_id = registered['driverId']
        for kind in ('LICENCE', 'INSURANCE', 'REGISTRATION', 'INSPECTION'):
            fleet.submit_document(driver_id, kind, {
                'filename': 'test.pdf', 'mime': 'application/pdf', 'expiryDate': '2030-01-01',
                'revision': 0, 'contentBase64': base64.b64encode(b'%PDF-1.4\nTest').decode()})
            fleet.review_document(driver_id, kind, {'status': 'APPROVED', 'note': '', 'revision': 1})
        fleet.approve(driver_id, {'status': 'APPROVED'})
        fleet.presence(driver_id, {'online': True, 'latitude': latitude, 'longitude': -123.1187})
        return driver_id

    def test_explicit_decline_is_not_reoffered_while_ride_is_unchanged(self):
        first = self._ready_driver('A', 49.2819)
        second = self._ready_driver('B', 49.31)
        quote = self.service.quote('passenger', self.request)
        ride = self.service.create('passenger', {'quoteToken': quote['quoteToken'],
                                                  'rideOption': {'tier': 'ECONOMY'}})
        offer = self.service.fleet.offer(first)
        self.assertEqual(offer['id'], ride['id'])
        self.service.fleet.action(first, ride['id'], 'decline', {})
        self.now += 3_600_000
        self.service.fleet.location(first, {'latitude': 49.2819, 'longitude': -123.1187})
        self.service.fleet.location(second, {'latitude': 49.31, 'longitude': -123.1187})
        self.assertEqual(self.service.fleet.offer(first), {})
        self.assertEqual(self.service.fleet.offer(second)['id'], ride['id'])


if __name__ == '__main__':
    unittest.main()
