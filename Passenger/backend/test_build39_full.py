"""Build 39 operational pagination / permission integration regression tests."""
import unittest
from test_build38_39 import StaffBuild3839Tests

class Build39OperationsTests(unittest.TestCase):
    setUp=StaffBuild3839Tests.setUp
    tearDown=StaffBuild3839Tests.tearDown
    call=StaffBuild3839Tests.call
    owner=StaffBuild3839Tests.owner
    def test_fleet_pagination_search_and_role_enforcement(self):
        with self.service.connect() as db:
            for i in range(53):
                db.execute('INSERT INTO fleet_drivers(id,name,vehicle,plate,category,status,created_ms) VALUES (?,?,?,?,?,?,?)',
                           (f'drv_page_{i:03}',f'Test Driver {i}','Sedan',f'BC{i:03}','ECONOMY','PENDING' if i%2 else 'SUSPENDED',100+i))
        owner=self.owner()
        status,first=self.call('/v2/fleet/admin/drivers?paged=1&limit=25',token=owner)
        self.assertEqual(status,200)
        self.assertEqual((first['total'],first['pages'],len(first['drivers'])),(53,3,25))
        status,last=self.call('/v2/fleet/admin/drivers?paged=1&page=3&limit=25',token=owner)
        self.assertEqual((status,len(last['drivers'])),(200,3))
        self.assertFalse({x['id'] for x in first['drivers']} & {x['id'] for x in last['drivers']})
        status,filtered=self.call('/v2/fleet/admin/drivers?paged=1&status=PENDING&q=Driver',token=owner)
        self.assertEqual((status,filtered['total']),(200,26))
        self.assertTrue(all(x['status']=='PENDING' for x in filtered['drivers']))
        self.assertEqual(self.call('/v2/fleet/admin/drivers?paged=1&page=0',token=owner)[0],400)
        self.assertEqual(self.call('/v2/fleet/admin/drivers?paged=1&status=INVALID',token=owner)[0],400)
        _,staff=self.call('/v1/staff/accounts',token=owner,body={'username':'finance_page','password':'long-finance-test-password','role':'FINANCE'})
        _,login=self.call('/v1/staff/login',body={'username':'finance_page','password':'long-finance-test-password'})
        self.assertEqual(self.call('/v2/fleet/admin/drivers?paged=1',token=login['accessToken'])[0],403)

    def test_support_pagination_search_and_role_enforcement(self):
        with self.service.connect() as db:
            for i in range(59):
                db.execute('INSERT INTO support_cases(id,ride_id,reporter_role,reporter_id,category,description,status,admin_note,created_ms,updated_ms) VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (f'case_page_{i:03}',f'ride_{i:03}','PASSENGER','reporter','OTHER',f'Issue number {i}', 'OPEN' if i%2 else 'RESOLVED','',100+i,100+i))
        owner=self.owner()
        status,first=self.call('/v1/admin/support-cases?paged=1&limit=25',token=owner)
        self.assertEqual((status,first['total'],first['pages'],len(first['cases'])),(200,59,3,25))
        _,last=self.call('/v1/admin/support-cases?paged=1&page=3&limit=25',token=owner)
        self.assertEqual(len(last['cases']),9)
        self.assertFalse({x['id'] for x in first['cases']} & {x['id'] for x in last['cases']})
        _,filtered=self.call('/v1/admin/support-cases?paged=1&status=OPEN&q=Issue',token=owner)
        self.assertEqual(filtered['total'],29)
        self.assertTrue(all(x['status']=='OPEN' for x in filtered['cases']))
        self.assertEqual(self.call('/v1/admin/support-cases?paged=1&limit=101',token=owner)[0],400)
        self.assertEqual(self.call('/v1/admin/support-cases?paged=1&status=INVALID',token=owner)[0],400)
        self.assertEqual(self.call('/v1/admin/support-cases?paged=1',token='not-valid')[0],401)

    def test_staff_ui_provides_operational_pagers_and_no_compliance_driver_mutation(self):
        import urllib.request
        with urllib.request.urlopen(self.base+'/admin') as r: html=r.read().decode()
        for control in ['fleet-page-info','support-page-info','fleet-search','support-search','role-preview']:
            self.assertIn('id="'+control+'"',html)
        self.assertIn("['OWNER','OPERATIONS','DEVELOPMENT'].includes(currentRole)?['APPROVED','PENDING','SUSPENDED']:[]",html)
