import unittest
from concurrent.futures import ThreadPoolExecutor

import test_build29 as previous
from fleet35 import FleetError
from fleet29 import KINDS


class Build35Tests(unittest.TestCase):
    setUp = previous.Build29Tests.setUp
    tearDown = previous.Build29Tests.tearDown
    document = previous.Build29Tests.document
    book = previous.Build29Tests.book

    def account(self, suffix, latitude=49.28, requested='XL'):
        result = self.fleet.register_account({
            'name': 'Radar Driver ' + suffix, 'vehicle': '2025 Test Vehicle',
            'plate': 'R35' + suffix, 'category': requested,
            'username': 'radar.' + suffix, 'phone': '60455501' + suffix.zfill(2),
            'password': 'Build-35-password'
        })
        driver = result['driverId']
        for kind in KINDS:
            self.fleet.submit_document(driver, kind, self.document())
            self.fleet.review_document(driver, kind, {'revision': 1, 'status': 'APPROVED'})
        self.fleet.approve(driver, {'status': 'APPROVED'})
        self.fleet.presence(driver, {'online': True, 'latitude': latitude, 'longitude': -123.12})
        return result

    def test_signup_cannot_self_assign_xl_and_admin_controls_categories(self):
        account = self.account('01', requested='XL')
        driver = account['driverId']
        self.assertEqual(account['eligibleCategories'], ['ECONOMY'])
        self.assertEqual(self.fleet.status(driver)['eligibleCategories'], ['ECONOMY'])
        self.fleet.set_eligibility(driver, {'categories': ['COMFORT', 'XL']})
        self.assertEqual(self.fleet.status(driver)['eligibleCategories'], ['COMFORT', 'ECONOMY', 'XL'])

    def test_shared_radar_first_atomic_claim_wins(self):
        first = self.account('02')['driverId']
        second = self.account('03', 49.281)['driverId']
        ride = self.book()
        one, two = self.fleet.offer(first), self.fleet.offer(second)
        self.assertEqual((one['id'], two['id']), (ride['id'], ride['id']))
        self.assertEqual(one['offerMode'], 'RADAR')
        self.assertEqual(one['nearbyDriverCount'], 2)
        def accept(driver):
            try:
                self.fleet.accept(driver, ride['id']); return driver
            except FleetError:
                return None
        with ThreadPoolExecutor(2) as pool:
            winners = [item for item in pool.map(accept, (first, second)) if item]
        self.assertEqual(len(winners), 1)
        self.assertEqual(self.service.get('p', ride['id'])['fleetDriverId'], winners[0])

    def test_unclaimed_radar_falls_back_to_exclusive_offer(self):
        first = self.account('04')['driverId']
        second = self.account('05', 49.281)['driverId']
        ride = self.book()
        self.assertEqual(self.fleet.offer(first)['offerMode'], 'RADAR')
        self.now += 12_001
        offer = self.fleet.offer(first)
        self.assertEqual(offer['id'], ride['id'])
        self.assertEqual(offer['offerMode'], 'EXCLUSIVE')
        self.assertEqual(self.fleet.offer(second), {})

    def test_history_uses_exact_pickup_address_and_route_points(self):
        driver = self.account('06')['driverId']
        self.request['pickup']['name'] = 'Current location'
        self.request['pickup']['address'] = '800 Robson Street, Vancouver, BC'
        ride = self.book()
        self.fleet.offer(driver); self.fleet.accept(driver, ride['id'])
        self.fleet.action(driver, ride['id'], 'arrive', {})
        pin = self.service.get('p', ride['id'])['pin']
        self.fleet.action(driver, ride['id'], 'start', {'pin': pin})
        self.fleet.action(driver, ride['id'], 'complete', {})
        trip = self.fleet.history(driver)['trips'][0]
        self.assertEqual(trip['pickup'], '800 Robson Street, Vancouver, BC')
        self.assertGreaterEqual(len(trip['routePoints']), 2)
        self.assertIn('pickupPoint', trip)


if __name__ == '__main__':
    unittest.main()
