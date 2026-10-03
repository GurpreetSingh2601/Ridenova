import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import test_build33 as previous_tests
from experience34 import ExperienceError
from server import Service, make_handler


class Build34Tests(unittest.TestCase):
    setUp = previous_tests.Build33Tests.setUp
    tearDown = previous_tests.Build33Tests.tearDown
    register = previous_tests.Build33Tests.register
    document = previous_tests.Build33Tests.document
    book = previous_tests.Build33Tests.book
    assigned = previous_tests.Build33Tests.assigned

    def experience_error(self, code, action):
        with self.assertRaises(ExperienceError) as raised:
            action()
        self.assertEqual(raised.exception.code, code)

    def completed(self):
        driver, ride = self.assigned()
        self.fleet.action(driver, ride, 'arrive', {})
        self.fleet.action(driver, ride, 'start', {'pin': self.service.get('p', ride)['pin']})
        self.fleet.action(driver, ride, 'complete', {})
        return driver, ride

    def test_both_sides_rate_completed_ride_and_can_update(self):
        driver, ride = self.completed()
        passenger = self.service.experience.rate('PASSENGER', 'p', ride, {
            'stars': 5, 'tags': ['SAFE_DRIVING', 'ON_TIME'], 'comment': 'Excellent ride'})
        self.assertEqual(passenger['rating']['stars'], 5)
        driver_view = self.service.experience.rate('DRIVER', driver, ride, {
            'stars': 4, 'tags': ['RESPECTFUL'], 'comment': 'Easy pickup'})
        self.assertEqual(driver_view['rating']['stars'], 4)
        updated = self.service.experience.rate('PASSENGER', 'p', ride, {
            'stars': 4, 'tags': ['FRIENDLY'], 'comment': 'Updated'})
        self.assertEqual(updated['rating']['stars'], 4)
        with self.service.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ride_feedback').fetchone()[0], 2)

    def test_rating_authorization_validation_and_completion_gate(self):
        driver, ride = self.assigned()
        self.experience_error('RIDE_NOT_COMPLETED', lambda: self.service.experience.rate(
            'PASSENGER', 'p', ride, {'stars': 5}))
        self.experience_error('RIDE_NOT_FOUND', lambda: self.service.experience.ride_experience(
            'PASSENGER', 'other', ride))
        self.experience_error('RIDE_NOT_FOUND', lambda: self.service.experience.ride_experience(
            'DRIVER', 'other-driver', ride))
        self.experience_error('INVALID_RATING', lambda: self.service.experience.rate(
            'PASSENGER', 'p', ride, {'stars': 6}))
        self.assertEqual(driver, self.service.get('p', ride)['fleetDriverId'])

    def test_support_cases_are_private_persistent_and_admin_managed(self):
        driver, ride = self.completed()
        case = self.service.experience.create_case('PASSENGER', 'p', {
            'rideId': ride, 'category': 'LOST_ITEM', 'description': 'I left a blue bag in the vehicle.'})
        self.assertEqual(case['status'], 'OPEN')
        self.assertEqual(self.service.experience.list_cases('DRIVER', driver)['cases'], [])
        reviewed = self.service.experience.update_case(case['id'], {
            'status': 'IN_REVIEW', 'adminNote': 'Driver contact requested'})
        self.assertEqual(reviewed['status'], 'IN_REVIEW')
        restarted = Service(self.service.database, clock=lambda: self.now)
        passenger_cases = restarted.experience.list_cases('PASSENGER', 'p')['cases']
        self.assertEqual(passenger_cases[0]['adminNote'], 'Driver contact requested')
        self.assertNotIn('reporterId', passenger_cases[0])

    def test_dashboard_counts_feedback_and_case_states(self):
        driver, ride = self.completed()
        self.service.experience.rate('PASSENGER', 'p', ride, {'stars': 5, 'tags': [], 'comment': ''})
        case = self.service.experience.create_case('DRIVER', driver, {
            'rideId': ride, 'category': 'APP', 'description': 'The route screen refreshed slowly.'})
        dashboard = self.service.admin_overview()['experience']
        self.assertEqual(dashboard['ratingCount'], 1)
        self.assertEqual(dashboard['averageRating'], 5.0)
        self.assertEqual(dashboard['openCases'], 1)
        self.service.experience.update_case(case['id'], {'status': 'RESOLVED', 'adminNote': 'Reviewed'})
        self.assertEqual(self.service.experience.dashboard()['resolvedCases'], 1)

    def test_http_contract_for_build34_experience(self):
        driver, ride = self.completed()
        account = self.service.verify_otp({'challengeId': self.service.request_otp({'phone': '6045550199'})['challengeId'],
                                           'code': '246810'}, 'p')
        token = account['accessToken']
        fleet_token = self.fleet.rotate_token(driver)['developmentToken']
        with patch.dict(os.environ, {'RIDENOVA_OWNER_USERNAME':'', 'RIDENOVA_OWNER_PASSWORD':''}):
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def call(path, method='GET', body=None, bearer=''):
            request = urllib.request.Request(
                f'http://127.0.0.1:{server.server_port}{path}', method=method,
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + bearer})
            try:
                with urllib.request.urlopen(request) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)

        try:
            self.assertEqual(call('/health')[1]['version'], '42.1')
            code, result = call(f'/v1/passenger/rides/{ride}/rating', 'POST',
                                {'stars': 5, 'tags': ['SAFE_DRIVING'], 'comment': 'Great'}, token)
            self.assertEqual(code, 200)
            self.assertEqual(result['rating']['stars'], 5)
            self.assertEqual(call(f'/v2/fleet/driver/rides/{ride}/rating', 'POST',
                                  {'stars': 5, 'tags': ['RESPECTFUL'], 'comment': ''}, fleet_token)[0], 200)
            with patch.dict(os.environ, {'RIDENOVA_DEV_ADMIN_TOKEN': 'admin-build34'}):
                self.assertEqual(call('/v1/admin/feedback', bearer='admin-build34')[0], 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
