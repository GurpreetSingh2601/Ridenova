import hashlib
import unittest
import test_server
from server import ACCESS_TTL_MS, DEV_OTP, OTP_TTL_MS, REFRESH_TTL_MS, Service


class AuthenticationTests(unittest.TestCase):
    setUp = test_server.BackendTests.setUp
    tearDown = test_server.BackendTests.tearDown
    error = test_server.BackendTests.error
    def challenge(self, phone='+16045550123'):
        return self.service.request_otp({'phone': phone})

    def verify(self, challenge=None, legacy_owner=None):
        challenge = challenge or self.challenge()
        return self.service.verify_otp({'challengeId': challenge['challengeId'], 'code': DEV_OTP}, legacy_owner)

    def test_phone_normalization_and_validation(self):
        for value in ('6045550123', '1 (604) 555-0123', '+1 604 555 0123'):
            self.assertEqual(self.service.normalize_phone(value), '+16045550123')
        for value in (None, '', '123', '+26045550123', '1045550123'):
            self.error('INVALID_PHONE', lambda value=value: self.service.normalize_phone(value))

    def test_otp_rate_limit_expiry_and_reuse(self):
        challenge = self.challenge()
        self.error('OTP_RATE_LIMITED', self.challenge)
        self.now += OTP_TTL_MS
        self.error('OTP_EXPIRED', lambda: self.verify(challenge))
        new_challenge = self.challenge()
        self.verify(new_challenge)
        self.error('OTP_ALREADY_USED', lambda: self.verify(new_challenge))

    def test_wrong_code_attempt_limit(self):
        challenge = self.challenge()
        for _ in range(5):
            self.error('OTP_INCORRECT', lambda: self.service.verify_otp({'challengeId': challenge['challengeId'], 'code': '000000'}, None))
        self.error('OTP_ATTEMPTS_EXCEEDED', lambda: self.verify(challenge))

    def test_account_is_reused_and_profile_updates(self):
        first = self.verify()
        profile = self.service.profile(first['passenger']['id'], {'firstName': ' Gurpreet ', 'lastName': ' Singh ', 'email': 'G@Example.CA'})
        self.assertEqual(profile['email'], 'g@example.ca')
        self.assertTrue(profile['profileComplete'])
        self.now += 60001
        second = self.verify(self.challenge())
        self.assertFalse(second['isNewAccount'])
        self.assertEqual(second['passenger']['id'], first['passenger']['id'])
        self.assertEqual(second['passenger']['firstName'], 'Gurpreet')

    def test_profile_validation(self):
        account = self.verify()['passenger']['id']
        self.error('INVALID_PROFILE', lambda: self.service.profile(account, {'firstName': '', 'lastName': 'Rider', 'email': ''}))
        self.error('INVALID_EMAIL', lambda: self.service.profile(account, {'firstName': 'Test', 'lastName': 'Rider', 'email': 'bad'}))

    def test_access_refresh_rotation_and_logout(self):
        session = self.verify()
        passenger_id = self.service.authenticate('Bearer ' + session['accessToken'])
        self.assertEqual(passenger_id, session['passenger']['id'])
        self.now += ACCESS_TTL_MS
        self.error('ACCESS_EXPIRED', lambda: self.service.authenticate('Bearer ' + session['accessToken']))
        replacement = self.service.refresh({'refreshToken': session['refreshToken']})
        self.assertEqual(self.service.authenticate('Bearer ' + replacement['accessToken']), passenger_id)
        self.error('REFRESH_EXPIRED', lambda: self.service.refresh({'refreshToken': session['refreshToken']}))
        self.service.logout('Bearer ' + replacement['accessToken'], replacement['refreshToken'])
        self.error('ACCESS_EXPIRED', lambda: self.service.authenticate('Bearer ' + replacement['accessToken']))
        self.error('REFRESH_EXPIRED', lambda: self.service.refresh({'refreshToken': replacement['refreshToken']}))

    def test_refresh_expiry(self):
        session = self.verify()
        self.now += REFRESH_TTL_MS
        self.error('REFRESH_EXPIRED', lambda: self.service.refresh({'refreshToken': session['refreshToken']}))

    def test_legacy_rides_migrate_once(self):
        legacy_session = 'legacy-development-session-0001'
        legacy_owner = hashlib.sha256(legacy_session.encode()).hexdigest()
        quote = self.service.quote(legacy_owner, self.request)
        ride = self.service.create(legacy_owner, {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'}})
        session = self.verify(legacy_owner=legacy_owner)
        account = session['passenger']['id']
        self.assertEqual(self.service.list(account)['rides'][0]['id'], ride['id'])
        self.assertEqual(self.service.list(legacy_owner)['rides'], [])

    def test_missing_and_malformed_bearer(self):
        for header in (None, '', 'Basic abc', 'Bearer ', 'Bearer ' + 'x' * 300):
            self.error('AUTH_REQUIRED', lambda header=header: self.service.authenticate(header))


if __name__ == '__main__':
    unittest.main()
