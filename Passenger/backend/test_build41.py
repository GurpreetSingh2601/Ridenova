import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from database import translate
from settings import Settings
from tools.import_sqlite import row_digest
from wsgi import create_app


class Build41SettingsTests(unittest.TestCase):
    def configuration(self):
        return {'RIDENOVA_ENVIRONMENT': 'staging', 'DATABASE_URL': 'postgresql://test/test',
                'RIDENOVA_PUBLIC_ORIGIN': 'https://test.example',
                'RIDENOVA_STAGING_TESTERS': '{"+16045550123":"736291"}',
                'RIDENOVA_STAGING_DRIVER_PHONES': '+16045550124', 'RIDENOVA_RATE_SECRET': 'a'*40}

    def test_fail_closed_production_and_missing_secrets(self):
        with self.assertRaises(ValueError): Settings.load({'RIDENOVA_ENVIRONMENT': 'production'})
        for key in self.configuration():
            if key == 'RIDENOVA_ENVIRONMENT': continue
            data = self.configuration(); data.pop(key)
            with self.assertRaises((ValueError, KeyError), msg=key): Settings.load(data)

    def test_staging_rejects_development_otp_token_and_plain_http(self):
        for key, value in [('RIDENOVA_STAGING_TESTERS', '{"+16045550123":"246810"}'),
                           ('RIDENOVA_DEV_ADMIN_TOKEN', 'anything'),
                           ('RIDENOVA_PUBLIC_ORIGIN', 'http://test.example'),
                           ('RIDENOVA_PUBLIC_ORIGIN', 'https://user:secret@test.example')]:
            data = self.configuration(); data[key] = value
            with self.assertRaises(ValueError): Settings.load(data)
        self.assertEqual(Settings.load(self.configuration()).environment, 'staging')

    def test_sql_translation_preserves_parameters_and_conflict_keys(self):
        self.assertEqual(translate("SELECT '?' WHERE id=?"), "SELECT '?' WHERE id=%s")
        self.assertIn('pg_advisory_xact_lock', translate('BEGIN IMMEDIATE'))
        sql = translate('INSERT OR REPLACE INTO fleet_declines VALUES (?,?,?)')
        self.assertIn('ON CONFLICT (driver_id,ride_id) DO UPDATE SET until_ms=EXCLUDED.until_ms', sql)
        self.assertIn('ON CONFLICT DO NOTHING', translate('INSERT OR IGNORE INTO development_earnings VALUES (?)'))
        self.assertIn("payload::jsonb->>'status'", translate("SELECT json_extract(payload,'$.status') FROM rides"))
        self.assertIn("'OPEN'", translate('SELECT ride_id FROM fleet_radar WHERE status="OPEN"'))
        with self.assertRaises(ValueError): translate('ALTER TABLE rides ADD COLUMN x TEXT')

    def test_digest_handles_binary_and_row_order(self):
        self.assertEqual(row_digest([(1, b'abc'), (2, None)]), row_digest([(2, None), (1, memoryview(b'abc'))]))
        self.assertNotEqual(row_digest([(1, b'abc')]), row_digest([(1, b'abd')]))


class Build41TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings('staging', str(Path(self.temp.name)/'db.sqlite'), 'https://test.example',
                                 {'+16045550123': '736291'}, ('+16045550124',), 'a'*40)
        self.migrate = patch('migrate.check'); self.migrate.start(); self.addCleanup(self.migrate.stop)
        self.rate = patch('operations.allow_requests', return_value=True); self.allow = self.rate.start(); self.addCleanup(self.rate.stop)
        with patch.dict('os.environ', {'RIDENOVA_OWNER_USERNAME': '', 'RIDENOVA_OWNER_PASSWORD': ''}):
            self.app = create_app(self.settings)
        self.addCleanup(self.temp.cleanup)

    def call(self, path, body=None, method=None, **overrides):
        data = b'' if body is None else json.dumps(body).encode()
        environ = {'REQUEST_METHOD': method or ('GET' if body is None else 'POST'), 'PATH_INFO': path,
                   'wsgi.input': io.BytesIO(data), 'CONTENT_LENGTH': str(len(data)),
                   'CONTENT_TYPE': 'application/json', 'wsgi.url_scheme': 'https', 'HTTP_HOST': 'test.example'}
        environ.update(overrides)
        result = {}
        def start(status, headers): result.update(status=int(status.split()[0]), headers=dict(headers))
        result['body'] = b''.join(self.app(environ, start))
        if result['headers'].get('Content-Type', '').startswith('application/json'):
            result['json'] = json.loads(result['body'])
        return result

    def test_health_is_liveness_and_readiness_detects_worker_failure(self):
        out = self.call('/health', **{'wsgi.url_scheme': 'http', 'HTTP_HOST': 'internal'})
        self.assertEqual(out['json']['build'], 42)
        with patch('operations.ready', return_value=False): self.assertEqual(self.call('/ready')['status'], 503)
        with patch('operations.ready', return_value=True): self.assertEqual(self.call('/ready')['status'], 200)

    def test_https_host_origin_methods_and_headers(self):
        self.assertEqual(self.call('/admin', **{'wsgi.url_scheme': 'http'})['status'], 400)
        self.assertEqual(self.call('/admin', HTTP_HOST='evil.example')['status'], 403)
        self.assertEqual(self.call('/admin', HTTP_ORIGIN='https://evil.example')['status'], 403)
        self.assertEqual(self.call('/admin', method='DELETE')['status'], 405)
        out = self.call('/admin')
        self.assertIn(b'STAGING - invited tests only', out['body'])
        self.assertEqual(out['headers']['X-Frame-Options'], 'DENY')
        self.assertIn('Strict-Transport-Security', out['headers'])

    def test_no_fixed_otp_or_public_registration_in_staging(self):
        request = self.call('/v1/auth/request-otp', {'phone': '6045550123'})
        self.assertEqual(request['status'], 200)
        self.assertNotIn('developmentCode', request['json'])
        challenge = request['json']['challengeId']
        self.assertEqual(self.call('/v1/auth/verify-otp', {'challengeId': challenge, 'code': '246810'})['status'], 401)
        verified = self.call('/v1/auth/verify-otp', {'challengeId': challenge, 'code': '736291'})
        self.assertEqual(verified['status'], 200)
        token = verified['json']['accessToken']
        self.assertEqual(self.call('/v1/passenger/me', HTTP_AUTHORIZATION='Bearer '+token)['status'], 200)
        self.assertEqual(self.call('/v1/auth/request-otp', {'phone': '6045550199'})['status'], 403)
        for path in ['/v2/fleet/register', '/v2/fleet/auth/register', '/v2/fleet/auth/recover',
                     '/v1/driver/status', '/v1/admin/rides/test/transition']:
            self.assertEqual(self.call(path, {})['status'], 403)

    def test_staff_still_requires_authentication_and_rate_limit_fails_closed(self):
        self.assertEqual(self.call('/v1/admin/overview')['status'], 401)
        self.allow.return_value = False
        self.assertEqual(self.call('/v1/staff/login', {'username': 'x', 'password': 'y'})['status'], 429)
        self.allow.side_effect = RuntimeError('secret must not appear')
        with self.assertLogs('ridenova', level='ERROR') as logs:
            response = self.call('/v1/staff/login', {})
        self.assertEqual(response['status'], 503)
        self.assertNotIn('secret must not appear', str(logs.output) + response['body'].decode())

    def test_oversize_body_rejected_before_reading(self):
        class Unreadable:
            def read(self, *_): raise AssertionError('Body should not be read')
        out = self.call('/v1/passenger/rides', {}, CONTENT_LENGTH='9999999', **{'wsgi.input': Unreadable()})
        self.assertEqual(out['status'], 413)

    def test_compliance_overview_cannot_leak_rides(self):
        from staff38 import Staff
        staff = Staff(self.settings.database)
        with staff.connect() as db:
            staff._create(db, 'compliance-test', 'long-unique-test-password', 'COMPLIANCE', 'test-fixture')
        session = staff.login({'username': 'compliance-test', 'password': 'long-unique-test-password'})
        response = self.call('/v1/admin/overview', HTTP_AUTHORIZATION='Bearer '+session['accessToken'])
        self.assertEqual(response['status'], 200)
        self.assertNotIn('rides', response['json'])
        self.assertNotIn('ledger', response['json'])


if __name__ == '__main__': unittest.main()
