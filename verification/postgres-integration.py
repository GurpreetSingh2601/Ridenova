"""Destructive tests ONLY against explicitly configured disposable *_test databases.
Run with RIDENOVA_TEST_DATABASE_URL and RIDENOVA_TEST_RESTORE_DATABASE_URL.
No production/staging fallback. A missing database is a failure, never a pass.
"""
import json
import multiprocessing
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Passenger/backend'))
import psycopg
from psycopg import sql
import test_build35 as legacy
from database import request_lock
from migrate import apply, check
from server import Service
from staff38 import Staff
from tools.import_sqlite import import_database
from tools.backup_restore import backup, restore


def test_database(key):
    value = os.environ.get(key, '')
    if not value.startswith(('postgres://', 'postgresql://')) or not urlsplit(value).path.endswith('_test'):
        raise SystemExit(key + ' must name a disposable PostgreSQL database ending in _test')
    return value


DATABASE = test_database('RIDENOVA_TEST_DATABASE_URL')
RESTORE = test_database('RIDENOVA_TEST_RESTORE_DATABASE_URL')
if DATABASE == RESTORE: raise SystemExit('Test and restore databases must differ')


def empty(database):
    with psycopg.connect(database) as db:
        tables = [r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename!='schema_migrations'")]
        if tables:
            db.execute(sql.SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(sql.SQL(',').join(map(sql.Identifier, tables))))


def process_accept(database, driver, ride, now, queue):
    try:
        service = Service(database, clock=lambda: now)
        with request_lock(database):
            service.fleet.accept(driver, ride)
        queue.put('accepted')
    except Exception as exc:
        queue.put(type(exc).__name__)


class PostgresDispatchTests(legacy.Build35Tests):
    def setUp(self):
        empty(DATABASE)
        self.now = 1_800_000_000_000
        self.service = Service(DATABASE, clock=lambda: self.now)
        self.fleet = self.service.fleet
        self.request = {'pickup': {'name': 'A', 'address': 'Vancouver', 'latitude': 49.28, 'longitude': -123.12},
                        'destination': {'name': 'B', 'address': 'Burnaby', 'latitude': 49.25, 'longitude': -122.98}, 'scheduled': False}
    def tearDown(self): pass

    def test_independent_process_acceptance(self):
        first = self.account('21')['driverId']; second = self.account('22', 49.281)['driverId']
        ride = self.book()
        self.fleet.offer(first); self.fleet.offer(second)
        context = multiprocessing.get_context('spawn'); queue = context.Queue()
        workers = [context.Process(target=process_accept, args=(DATABASE, driver, ride['id'], self.now, queue)) for driver in (first, second)]
        for worker in workers: worker.start()
        for worker in workers:
            worker.join(30)
            if worker.is_alive(): worker.terminate(); worker.join(); self.fail('Acceptance deadlocked')
            self.assertEqual(worker.exitcode, 0)
        outcomes = [queue.get(timeout=5) for _ in workers]
        self.assertEqual(outcomes.count('accepted'), 1, outcomes)
        self.assertEqual(outcomes.count('FleetError'), 1, outcomes)
        queue.close()

    def test_duplicate_booking_and_completion_survive_new_service(self):
        driver = self.account('23')['driverId']
        quote = self.service.quote('p', self.request)
        body = {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'}}
        ride = self.service.create('p', body)
        self.assertEqual(Service(DATABASE).create('p', body)['id'], ride['id'])
        self.fleet.offer(driver); self.fleet.accept(driver, ride['id'])
        self.fleet.action(driver, ride['id'], 'arrive', {})
        self.fleet.action(driver, ride['id'], 'start', {'pin': self.service.get('p', ride['id'])['pin']})
        self.fleet.action(driver, ride['id'], 'complete', {})
        Service(DATABASE).fleet.action(driver, ride['id'], 'complete', {})
        with self.service.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM development_earnings WHERE ride_id=?', (ride['id'],)).fetchone()[0], 1)

    def test_stale_location_and_explicit_decline(self):
        driver = self.account('24')['driverId']; ride = self.book()
        self.now += 31000
        self.assertEqual(self.fleet.offer(driver), {})
        self.fleet.presence(driver, {'online': True, 'latitude': 49.28, 'longitude': -123.12})
        self.assertEqual(self.fleet.offer(driver)['id'], ride['id'])
        self.fleet.action(driver, ride['id'], 'decline', {})
        self.now += 61000
        self.fleet.presence(driver, {'online': True, 'latitude': 49.28, 'longitude': -123.12})
        self.assertEqual(self.fleet.offer(driver), {})


class PostgresMigrationTests(unittest.TestCase):
    def setUp(self): empty(DATABASE)

    def test_payment_methods_load_and_keep_added_order(self):
        # Exercise the same endpoint logic used by the staging payment screen.
        service = Service(DATABASE, clock=lambda: 1_800_000_000_000)
        challenge = service.request_otp({'phone': '+16045550123'})
        account = service.verify_otp({'challengeId': challenge['challengeId'],
                                      'code': challenge['developmentCode']}, None)
        owner = account['passenger']['id']
        first = service.payment_methods(owner)['paymentMethods'][0]
        second = service.add_payment_method(owner, {'brand': 'Mastercard', 'last4': '4444',
                                                     'expiryMonth': 10, 'expiryYear': 2032})
        third = service.add_payment_method(owner, {'brand': 'Amex', 'last4': '1234',
                                                    'expiryMonth': 11, 'expiryYear': 2033})
        service.update_payment_method(owner, third['id'], 'default')
        self.assertEqual([item['id'] for item in Service(DATABASE).payment_methods(owner)['paymentMethods']],
                         [first['id'], second['id'], third['id']])

    def test_migrations_reapply_without_changes(self):
        apply(DATABASE); check(DATABASE)
        with psycopg.connect(DATABASE) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0], 2)

    def test_import_preserves_data_and_refuses_occupied_target(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'source.sqlite3'
            service = Service(path); Staff(path)
            otp = service.request_otp({'phone': '6045550123'})
            account = service.verify_otp({'challengeId': otp['challengeId'], 'code': otp['developmentCode']}, None)
            report = import_database(path, DATABASE, Path(temp)/'report.json')
            self.assertEqual(report['tables']['passengers']['rows'], 1)
            pg = Service(DATABASE)
            self.assertEqual(pg.profile(account['passenger']['id'])['phone'], '+16045550123')
            with self.assertRaises(RuntimeError): import_database(path, DATABASE, Path(temp)/'again.json')
            self.assertEqual(service.authenticate('Bearer '+account['accessToken']), account['passenger']['id'])

    def test_backup_restore_checksum_and_refusal(self):
        with psycopg.connect(RESTORE) as db:
            db.execute('DROP SCHEMA public CASCADE'); db.execute('CREATE SCHEMA public')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'backup.dump'
            original = backup(DATABASE, path)
            result = restore(RESTORE, path)
            self.assertEqual(original, result)
            with self.assertRaises(RuntimeError): restore(RESTORE, path)
            with self.assertRaises(RuntimeError): backup(DATABASE, path)


if __name__ == '__main__':
    apply(DATABASE)
    unittest.main(verbosity=2)
