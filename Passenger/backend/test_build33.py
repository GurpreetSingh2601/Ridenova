import json
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer

import test_build30 as previous_tests
from fleet33 import FleetError
from server import make_handler


class Build33Tests(unittest.TestCase):
    setUp = previous_tests.Build30Tests.setUp
    tearDown = previous_tests.Build30Tests.tearDown
    error = previous_tests.Build30Tests.error
    register = previous_tests.Build30Tests.register
    document = previous_tests.Build30Tests.document
    book = previous_tests.Build30Tests.book
    assigned = previous_tests.Build30Tests.assigned

    def account(self, username='driver.33', phone='6045550133', password='Test-password-33'):
        return self.fleet.register_account({'name': 'Build 33 driver', 'vehicle': 'Test car',
            'plate': 'BUILD33', 'category': 'ECONOMY', 'username': username,
            'phone': phone, 'password': password})

    def test_phone_normalization_masking_and_sign_in(self):
        account = self.account(phone='+1 (604) 555-0133')
        self.assertEqual(account['maskedPhone'], '(***) ***-0133')
        signed = self.fleet.login({'identifier': '604-555-0133', 'password': 'Test-password-33'})
        self.assertEqual(signed['driverId'], account['driverId'])
        details = self.fleet.login_details(account['driverId'])
        self.assertEqual(details['maskedPhone'], '(***) ***-0133')
        self.assertNotIn('6045550133', json.dumps(details))

    def test_existing_build30_account_still_uses_username(self):
        account = self.fleet.register_account({'name': 'Existing', 'vehicle': 'Car', 'plate': 'OLD30',
            'category': 'ECONOMY', 'username': 'existing.30', 'password': 'Test-password-30'})
        self.assertFalse(self.fleet.login_details(account['driverId'])['phoneConfigured'])
        self.assertEqual(self.fleet.login({'username': 'existing.30', 'password': 'Test-password-30'})
                         ['driverId'], account['driverId'])

    def test_duplicate_phone_registration_is_atomic(self):
        self.account()
        self.error('PHONE_TAKEN', lambda: self.account('another.driver'))
        with self.service.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM fleet_drivers').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM fleet_documents').fetchone()[0], 4)

    def test_concurrent_phone_registration_has_one_winner(self):
        def attempt(index):
            try:
                self.account('driver.' + str(index))
                return True
            except FleetError:
                return False
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(attempt, range(2))), 1)

    def test_phone_validation(self):
        for phone in ('123', '1045550123', '6041550123'):
            self.error('INVALID_PHONE', lambda: self.account(phone=phone))

    def test_password_change_keeps_session_and_replaces_password(self):
        account = self.account()
        driver = account['driverId']
        self.error('CURRENT_PASSWORD_INCORRECT', lambda: self.fleet.change_password(driver, {
            'currentPassword': 'Wrong-password-33', 'newPassword': 'New-password-33'}))
        self.fleet.change_password(driver, {'currentPassword': 'Test-password-33',
                                             'newPassword': 'New-password-33'})
        self.assertEqual(self.fleet.authenticate('Bearer ' + account['developmentToken']), driver)
        self.error('INVALID_LOGIN', lambda: self.fleet.login({
            'identifier': 'driver.33', 'password': 'Test-password-33'}))
        self.assertEqual(self.fleet.login({'identifier': 'driver.33', 'password': 'New-password-33'})
                         ['driverId'], driver)

    def test_account_overview_uses_authoritative_account_data(self):
        account = self.account()
        overview = self.fleet.account_overview(account['driverId'])
        self.assertEqual(overview['documents']['required'], 4)
        self.assertEqual(overview['documents']['approved'], 0)
        self.assertEqual(overview['lifetime']['completedTrips'], 0)
        self.assertEqual(overview['maskedPhone'], '(***) ***-0133')

    def test_http_access_contract(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def call(path, body=None, token=None):
            request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (token or '')})
            try:
                with urllib.request.urlopen(request) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)
        try:
            self.assertEqual(call('/health')[1]['version'], '42.1')
            code, account = call('/v2/fleet/auth/register', {'username': 'http.33',
                'phone': '6045550134', 'password': 'Test-password-33', 'name': 'HTTP Driver',
                'vehicle': 'Car', 'plate': 'HTTP33', 'category': 'ECONOMY'})
            self.assertEqual(code, 200)
            token = account['developmentToken']
            self.assertEqual(call('/v2/fleet/driver/account-overview', token=token)[0], 200)
            self.assertEqual(call('/v2/fleet/driver/password', {
                'currentPassword': 'Test-password-33', 'newPassword': 'Changed-password-33'}, token)[0], 200)
            self.assertEqual(call('/v2/fleet/auth/login', {
                'identifier': '6045550134', 'password': 'Changed-password-33'})[0], 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
