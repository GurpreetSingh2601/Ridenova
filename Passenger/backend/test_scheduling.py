import copy
from concurrent.futures import ThreadPoolExecutor
import unittest
import test_server
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from server import make_handler


class SchedulingTests(unittest.TestCase):
    setUp = test_server.BackendTests.setUp
    tearDown = test_server.BackendTests.tearDown
    error = test_server.BackendTests.error
    booking = test_server.BackendTests.booking
    def scheduled(self, minutes=60):
        request = copy.deepcopy(self.request)
        request.update(scheduled=True, scheduledAtEpochMs=self.now + minutes * 60000, scheduleTimeZone='America/Vancouver')
        quote = self.service.quote(self.owner, request)
        return self.service.create(self.owner, {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'}})

    def test_scheduled_is_persisted_without_immediate_matching(self):
        ride = self.scheduled()
        self.assertEqual(ride['status'], 'SCHEDULED')
        self.assertEqual(ride['draft']['scheduledAtEpochMs'], self.now + 3600000)
        self.assertEqual(self.service.activate_due(), [])

    def test_exact_lead_and_horizon_boundaries(self):
        for minutes in (15, 30 * 24 * 60):
            self.assertEqual(self.scheduled(minutes)['status'], 'SCHEDULED')
        for delta in (15 * 60000 - 1, 30 * 86400000 + 1, -1):
            request = {**self.request, 'scheduled': True, 'scheduleTimeZone': 'UTC', 'scheduledAtEpochMs': self.now + delta}
            self.error('SCHEDULE_OUT_OF_RANGE', lambda: self.service.quote(self.owner, request))

    def test_timestamp_types_and_ride_now_stale_timestamp(self):
        for timestamp in (True, '10000000', float('nan'), 10000000.5, None):
            request = {**self.request, 'scheduled': True, 'scheduleTimeZone': 'UTC', 'scheduledAtEpochMs': timestamp}
            self.error('INVALID_SCHEDULE', lambda: self.service.quote(self.owner, request))
        request = {**self.request, 'scheduledAtEpochMs': self.now + 3600000}
        self.error('INVALID_SCHEDULE', lambda: self.service.quote(self.owner, request))

    def test_quote_schedule_cannot_be_changed_at_booking(self):
        request = {**self.request, 'scheduled': True, 'scheduleTimeZone': 'UTC', 'scheduledAtEpochMs': self.now + 3600000}
        quote = self.service.quote(self.owner, request)
        ride = self.service.create(self.owner, {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'},
                                               'draft': {'scheduledAtEpochMs': 1, 'scheduled': False}})
        self.assertEqual(ride['draft']['scheduledAtEpochMs'], request['scheduledAtEpochMs'])

    def test_scheduler_activation_boundary_and_once_only(self):
        ride = self.scheduled()
        self.now += 3599999
        self.assertEqual(self.service.activate_due(), [])
        self.now += 1
        with ThreadPoolExecutor(max_workers=4) as pool:
            changed = list(pool.map(lambda _: self.service.activate_due(), range(8)))
        self.assertEqual(sum(len(ids) for ids in changed), 1)
        updated = self.service.get(self.owner, ride['id'])
        self.assertEqual(updated['status'], 'SEARCHING')
        self.assertEqual(updated['graceEndsAtEpochMs'], self.now + 120000)

    def test_scheduled_cancellation_free_after_booking_grace(self):
        ride = self.scheduled()
        self.now += 180000
        self.assertEqual(self.service.cancel(self.owner, ride['id'])['cancellationFeeCad'], 0)
        self.now += 3600000
        self.assertEqual(self.service.activate_due(), [])

    def test_schedule_conflict_and_limit(self):
        self.scheduled(60)
        self.error('SCHEDULE_CONFLICT', lambda: self.scheduled(119))
        for minute in (120, 180, 240, 300):
            self.scheduled(minute)
        self.error('SCHEDULE_LIMIT', lambda: self.scheduled(360))

    def test_immediate_ride_coexists_but_delays_scheduled_activation(self):
        scheduled = self.scheduled()
        immediate = self.service.create(self.owner, self.booking())
        self.now += 3600000
        self.assertEqual(self.service.activate_due(), [])
        self.service.cancel(self.owner, immediate['id'])
        self.assertEqual(self.service.activate_due(), [scheduled['id']])

    def test_missed_schedule_expires_without_fee(self):
        ride = self.scheduled()
        self.now += 3600000 + 15 * 60000 + 1
        self.service.activate_due()
        expired = self.service.get(self.owner, ride['id'])
        self.assertEqual(expired['status'], 'SCHEDULE_EXPIRED')
        self.assertEqual(expired['cancellationFeeCad'], 0)
        self.error('INVALID_TRANSITION', lambda: self.service.transition(ride['id'], 'DRIVER_ASSIGNED'))

    def test_restart_recovers_schedule(self):
        from server import Service
        ride = self.scheduled()
        self.now += 3600000
        reopened = Service(self.service.database, clock=lambda: self.now)
        self.assertEqual(reopened.activate_due(), [ride['id']])
        self.assertEqual(reopened.activate_due(), [])

    def test_policy_snapshot_survives_configuration_change(self):
        request = {**self.request, 'scheduled': True, 'scheduleTimeZone': 'UTC', 'scheduledAtEpochMs': self.now + 3600000}
        quote = self.service.quote(self.owner, request)
        self.service.config['graceSeconds'] = 10
        self.service.config['cancellationFeeCents'] = 999
        ride = self.service.create(self.owner, {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'}})
        self.now += 3600000
        self.service.activate_due()
        self.now += 120001
        self.assertEqual(self.service.cancel(self.owner, ride['id'])['cancellationFeeCad'], 5)

    def test_http_schedule_to_activation_to_cancel(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        access = [None]
        def call(path, body=None, authenticated=True):
            headers = {'Content-Type': 'application/json', 'X-RideNova-Session': 'schedule-http-session-0001'}
            if authenticated and access[0]:
                headers['Authorization'] = 'Bearer ' + access[0]
            request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers=headers)
            with urllib.request.urlopen(request) as response:
                return json.load(response)
        try:
            challenge = call('/v1/auth/request-otp', {'phone': '+16045550124'}, authenticated=False)
            session = call('/v1/auth/verify-otp', {'challengeId': challenge['challengeId'], 'code': challenge['developmentCode']}, authenticated=False)
            access[0] = session['accessToken']
            quote = call('/v1/passenger/quotes', {**self.request, 'scheduled': True,
                'scheduledAtEpochMs': self.now + 900000, 'scheduleTimeZone': 'UTC'})
            ride = call('/v1/passenger/rides', {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'}})
            self.assertEqual(ride['status'], 'SCHEDULED')
            self.assertEqual(call('/v1/passenger/rides')['rides'][0]['status'], 'SCHEDULED')
            self.now += 900000
            self.service.activate_due()
            replacement = call('/v1/auth/refresh', {'refreshToken': session['refreshToken']}, authenticated=False)
            access[0] = replacement['accessToken']
            self.assertEqual(call('/v1/passenger/rides/' + ride['id'])['status'], 'SEARCHING')
            self.assertEqual(call('/v1/passenger/rides/' + ride['id'] + '/cancel', {})['cancellationFeeCad'], 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
