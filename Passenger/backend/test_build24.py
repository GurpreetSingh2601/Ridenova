import tempfile
import unittest
from pathlib import Path
from backend.server import Service

class Build24Tests(unittest.TestCase):
    def test_admin_overview_empty_and_ledger_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            svc = Service(Path(directory) / 'test.sqlite3')
            empty = svc.admin_overview()
            self.assertEqual(empty['rideCount'], 0)
            self.assertEqual(empty['totals']['totalCents'], 0)
            ride = {'id': 'rn_ledger_test', 'option': {'breakdown': {'subtotalCents': 1000,
                'gstCents': 50, 'totalCents': 1050, 'platformCommissionCents': 300,
                'driverGrossBeforeCostsCents': 700}}}
            with svc.connect() as db:
                svc.record_development_earning(db, ride)
                svc.record_development_earning(db, ride)
            result = svc.admin_overview()
            self.assertEqual(len(result['ledger']), 1)
            self.assertEqual(result['totals']['totalCents'], 1050)
            self.assertEqual(result['totals']['commissionCents'], 300)
            self.assertFalse(result['paymentProcessorConnected'])

if __name__ == '__main__':
    unittest.main()
