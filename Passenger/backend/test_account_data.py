import tempfile
import unittest
from pathlib import Path

from server import APIError, DEV_OTP, Service


class AccountDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1_800_000_000_000
        self.service = Service(Path(self.temp.name) / 'test.sqlite3', clock=lambda: self.now,
                               route_provider=lambda *_: {'distanceKm': 10, 'durationMinutes': 20,
                                                          'routeType': 'BEST', 'isApproximate': True})
        challenge = self.service.request_otp({'phone': '+16045550123'})
        result = self.service.verify_otp({'challengeId': challenge['challengeId'], 'code': DEV_OTP}, None)
        self.owner = result['passenger']['id']
        self.place = {'name': 'Home', 'address': '123 Test Street, Vancouver',
                      'latitude': 49.28, 'longitude': -123.12, 'placeId': 'place-home'}

    def tearDown(self):
        self.temp.cleanup()

    def assert_error(self, code, action):
        with self.assertRaises(APIError) as raised:
            action()
        self.assertEqual(raised.exception.code, code)

    def test_saved_places_and_recent_destinations_persist(self):
        self.service.change_saved_place(self.owner, {'slot': 'home', 'place': self.place})
        self.service.change_recent_destination(self.owner, {'action': 'add', 'place': self.place})
        updated = {**self.place, 'name': 'Home again'}
        self.now += 1
        self.service.change_recent_destination(self.owner, {'action': 'add', 'place': updated})
        data = Service(self.service.database, clock=lambda: self.now).account_places(self.owner)
        self.assertEqual(data['savedPlaces']['home']['address'], self.place['address'])
        self.assertEqual(len(data['recentDestinations']), 1)
        self.assertEqual(data['recentDestinations'][0]['name'], 'Home again')
        self.service.change_saved_place(self.owner, {'action': 'remove', 'slot': 'home'})
        self.service.change_recent_destination(self.owner, {'action': 'clear'})
        self.assertEqual(self.service.account_places(self.owner), {'savedPlaces': {}, 'recentDestinations': []})

    def test_recent_destinations_are_capped_at_eight(self):
        for index in range(10):
            self.now += 1
            place = {**self.place, 'name': f'Place {index}', 'address': f'{index} Test Street, Vancouver',
                     'placeId': f'place-{index}'}
            self.service.change_recent_destination(self.owner, {'action': 'add', 'place': place})
        recent = self.service.account_places(self.owner)['recentDestinations']
        self.assertEqual(len(recent), 8)
        self.assertEqual(recent[0]['name'], 'Place 9')

    def test_payment_methods_default_remove_and_limits(self):
        original = self.service.payment_methods(self.owner)['paymentMethods']
        self.assertEqual(len(original), 1)
        self.assertTrue(original[0]['isDefault'])
        added = self.service.add_payment_method(self.owner, {
            'brand': 'Mastercard', 'last4': '4444', 'expiryMonth': 10, 'expiryYear': 2032})
        selected = self.service.update_payment_method(self.owner, added['id'], 'default')
        self.assertTrue(selected['isDefault'])
        methods = self.service.payment_methods(self.owner)['paymentMethods']
        self.assertEqual([method['id'] for method in methods], [original[0]['id'], added['id']])
        self.assertFalse(methods[0]['isDefault'])
        self.assertTrue(methods[1]['isDefault'])
        # Refreshing the payment list, restarting the service and switching back
        # must not shuffle the card rows on screen.
        restarted = Service(self.service.database, clock=lambda: self.now)
        self.assertEqual([method['id'] for method in restarted.payment_methods(self.owner)['paymentMethods']],
                         [original[0]['id'], added['id']])
        self.service.update_payment_method(self.owner, original[0]['id'], 'default')
        self.assertEqual([method['id'] for method in self.service.payment_methods(self.owner)['paymentMethods']],
                         [original[0]['id'], added['id']])
        self.service.update_payment_method(self.owner, added['id'], 'default')
        self.service.update_payment_method(self.owner, original[0]['id'], 'remove')
        self.assert_error('LAST_PAYMENT_METHOD', lambda: self.service.update_payment_method(self.owner, added['id'], 'remove'))

    def test_selected_payment_is_snapshotted_and_completion_is_recorded(self):
        method = self.service.payment_methods(self.owner)['paymentMethods'][0]
        request = {'pickup': self.place, 'destination': {**self.place, 'name': 'Work',
                   'address': '456 Work Street, Vancouver', 'longitude': -123.1}, 'scheduled': False}
        quote = self.service.quote(self.owner, request)
        ride = self.service.create(self.owner, {'quoteToken': quote['quoteToken'],
            'rideOption': {'tier': 'ECONOMY'}, 'paymentMethodId': method['id']})
        self.assertEqual(ride['payment']['methodId'], method['id'])
        self.assertEqual(ride['payment']['status'], 'NOT_CHARGED')
        for status in ('DRIVER_ASSIGNED', 'DRIVER_ARRIVED', 'TRIP_STARTED', 'COMPLETED'):
            ride = self.service.transition(ride['id'], status)
        self.assertEqual(ride['payment']['status'], 'CAPTURED_DEMO')
        self.assertEqual(ride['payment']['amountCents'], ride['option']['breakdown']['totalCents'])


if __name__ == '__main__':
    unittest.main()
