import tempfile
import unittest
from server import Service
from fleet28 import Fleet, FleetError

class FleetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = [1000000]
        self.service = Service(self.tmp.name + '/fleet.db', clock=lambda: self.clock[0])
        self.fleet = Fleet(self.service)
    def tearDown(self):
        self.tmp.cleanup()
    def register(self):
        return self.fleet.register({'name':'Test Driver','vehicle':'Test Car','plate':'TEST','category':'ECONOMY'})
    def test_individual_token_and_status(self):
        reg = self.register()
        self.assertEqual(self.fleet.authenticate('Bearer '+reg['developmentToken']),reg['driverId'])
        with self.assertRaises(FleetError): self.fleet.authenticate('Bearer wrong')
        with self.assertRaises(FleetError): self.fleet.presence(reg['driverId'],{'online':True,'latitude':49.2,'longitude':-122.9})
        self.fleet.approve(reg['driverId'],{'status':'APPROVED'})
        self.fleet.presence(reg['driverId'],{'online':True,'latitude':49.2,'longitude':-122.9})
        self.assertEqual(self.fleet.offer(reg['driverId']),{})
        self.assertFalse(self.fleet.documents(reg['driverId'])['uploadSupported'])
        self.fleet.approve(reg['driverId'],{'status':'SUSPENDED'})
        with self.assertRaises(FleetError): self.fleet.presence(reg['driverId'],{'online':True,'latitude':49.2,'longitude':-122.9})
    def test_offer_expiry_and_atomic_reservation(self):
        a,b=self.register(),self.register()
        for r in (a,b):
            self.fleet.approve(r['driverId'],{'status':'APPROVED'})
            self.fleet.presence(r['driverId'],{'online':True,'latitude':49.28,'longitude':-123.12})
        from unittest.mock import patch
        req={'pickup':{'name':'A','address':'Vancouver','latitude':49.28,'longitude':-123.12},'destination':{'name':'B','address':'Burnaby','latitude':49.25,'longitude':-122.98},'scheduled':False}
        q=self.service.quote('passenger-a',req)
        ride=self.service.create('passenger-a',{'quoteToken':q['quoteToken'],'rideOption':{'tier':'ECONOMY'}})
        offer=self.fleet.offer(a['driverId'])
        self.assertEqual(offer['rideId'],ride['id'])
        self.assertEqual(offer['expiresAtEpochMs'],self.clock[0]+20000)
        self.assertEqual(self.fleet.offer(b['driverId']),{})
        self.assertEqual(self.fleet.accept(a['driverId'],ride['id'])['status'],'DRIVER_ASSIGNED')
        with self.assertRaises(FleetError):self.fleet.accept(b['driverId'],ride['id'])
        self.assertEqual(self.service.get('passenger-a',ride['id'])['fleetDriverId'],a['driverId'])
