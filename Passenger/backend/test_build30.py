import json
import os
import threading
import unittest
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import test_build29 as previous_tests
from server import Service, make_handler
from fleet30 import FleetError

class Build30Tests(unittest.TestCase):
    setUp=previous_tests.Build29Tests.setUp
    tearDown=previous_tests.Build29Tests.tearDown
    error=previous_tests.Build29Tests.error
    register=previous_tests.Build29Tests.register
    document=previous_tests.Build29Tests.document
    book=previous_tests.Build29Tests.book
    assigned=previous_tests.Build29Tests.assigned

    def account(self, username='driver.one', password='Test-password-30'):
        return self.fleet.register_account({'name':'Test driver','vehicle':'Test car','plate':'TEST30','category':'ECONOMY',
                                           'username':username,'password':password})
    def sign_in(self, username='driver.one', password='Test-password-30'):
        return self.fleet.login({'username':username,'password':password})
    def test_register_stores_hash_not_password(self):
        a=self.account()
        with self.service.connect() as db:
            row=db.execute('SELECT username,salt,password_hash FROM fleet_logins').fetchone()
        self.assertEqual(row[0],'driver.one');self.assertEqual(len(row[1]),32);self.assertEqual(len(row[2]),64)
        self.assertNotIn('Test-password-30',str(row))
        self.assertEqual(self.fleet.authenticate('Bearer '+a['developmentToken']),a['driverId'])
        self.assertTrue(self.fleet.status(a['driverId'])['loginConfigured'])
    def test_username_normalization_and_duplicate_atomicity(self):
        self.account(' Driver.One ')
        self.error('USERNAME_TAKEN',lambda:self.account('DRIVER.ONE'))
        with self.service.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM fleet_drivers').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM fleet_documents').fetchone()[0],4)
        self.assertEqual(self.sign_in(' DRIVER.ONE ')['username'],'driver.one')
    def test_username_password_and_profile_validation(self):
        for user in ('x','@bad','bad name','a'*41,None):
            self.error('INVALID_USERNAME',lambda:self.account(user))
        for password in ('short',' '*12,'x'*129,None):
            self.error('INVALID_PASSWORD',lambda:self.account(password=password))
        with self.service.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM fleet_drivers').fetchone()[0],0)
    def test_login_revokes_old_session(self):
        a=self.account();b=self.sign_in()
        self.assertEqual(a['driverId'],b['driverId']);self.assertNotEqual(a['developmentToken'],b['developmentToken'])
        self.error('FLEET_AUTH_REQUIRED',lambda:self.fleet.authenticate('Bearer '+a['developmentToken']))
        self.assertEqual(self.fleet.authenticate('Bearer '+b['developmentToken']),a['driverId'])
    def test_wrong_and_unknown_password_attempts_lock_and_reset(self):
        self.account()
        for username in ('driver.one','unknown.driver'):
            for _ in range(5):self.error('INVALID_LOGIN',lambda:self.sign_in(username,'Wrong-password-30'))
            self.error('LOGIN_LOCKED',lambda:self.sign_in(username))
        self.now+=60001
        self.assertEqual(self.sign_in()['username'],'driver.one')
    def test_failed_login_does_not_revoke_valid_session(self):
        a=self.account();self.error('INVALID_LOGIN',lambda:self.sign_in(password='Wrong-password-30'))
        self.assertEqual(self.fleet.authenticate('Bearer '+a['developmentToken']),a['driverId'])
    def test_existing_driver_can_add_login_without_new_profile(self):
        a=self.register();d=a['driverId']
        self.fleet.set_login(d,{'username':'existing.driver','password':'Test-password-30'})
        self.assertEqual(self.sign_in('existing.driver')['driverId'],d)
        self.assertTrue(self.fleet.status(d)['documentsReady']);self.assertEqual(self.fleet.status(d)['status'],'APPROVED')
        with self.service.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM fleet_drivers').fetchone()[0],1)
        self.error('LOGIN_EXISTS',lambda:self.fleet.set_login(d,{'username':'changed.driver','password':'Test-password-30'}))
    def test_legacy_logout_requires_login_setup(self):
        d=self.register()['driverId']
        self.error('LOGIN_REQUIRED',lambda:self.fleet.logout(d))
    def test_logout_offline_revocation_and_offer_release(self):
        a=self.register();d=a['driverId'];self.fleet.set_login(d,{'username':'existing','password':'Test-password-30'})
        self.book();self.assertTrue(self.fleet.offer(d))
        self.fleet.logout(d)
        self.assertFalse(self.fleet.status(d)['online'])
        with self.service.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM fleet_offers').fetchone()[0],0)
        self.error('FLEET_AUTH_REQUIRED',lambda:self.fleet.authenticate('Bearer '+a['developmentToken']))
        self.assertEqual(self.sign_in('existing')['driverId'],d)
    def test_active_trip_blocks_logout_without_revoking_token(self):
        a=self.register();d=a['driverId'];self.fleet.set_login(d,{'username':'active.driver','password':'Test-password-30'})
        ride=self.book();self.fleet.offer(d);self.fleet.accept(d,ride['id'])
        for action in ('assigned','arrive','start'):
            if action=='arrive':self.fleet.action(d,ride['id'],'arrive',{})
            if action=='start':self.fleet.action(d,ride['id'],'start',{'pin':self.service.get('p',ride['id'])['pin']})
            self.error('ACTIVE_RIDE',lambda:self.fleet.logout(d))
            self.assertEqual(self.fleet.authenticate('Bearer '+a['developmentToken']),d)
        self.fleet.action(d,ride['id'],'complete',{});self.fleet.logout(d)
        token=self.sign_in('active.driver')['developmentToken']
        self.assertEqual(self.fleet.authenticate('Bearer '+token),d)
        self.assertEqual(len(self.fleet.history(d)['trips']),1)
    def test_sign_in_recovers_active_ride_after_restart(self):
        d,r=self.assigned();self.fleet.set_login(d,{'username':'recover.trip','password':'Test-password-30'})
        restarted=Service(self.service.database,clock=lambda:self.now)
        signed=restarted.fleet.login({'username':'recover.trip','password':'Test-password-30'})
        self.assertEqual(signed['driverId'],d);self.assertEqual(restarted.fleet.active_ride(d)['id'],r)
    def test_account_switching_keeps_documents_isolated(self):
        a=self.account();b=self.account('driver.two');d=a['driverId']
        self.fleet.submit_document(d,'LICENCE',self.document())
        self.fleet.logout(d)
        signed=self.sign_in('driver.two');self.assertEqual(signed['driverId'],b['driverId'])
        self.assertTrue(all(x['status']=='NOT_SUBMITTED' for x in self.fleet.documents(b['driverId'])['documents']))
        self.assertTrue(any(x['status']=='PENDING' for x in self.fleet.documents(d)['documents']))
        self.assertEqual(self.fleet.history(b['driverId'])['trips'],[])
    def test_admin_reset_requires_recovery_and_invalidates_old_password(self):
        a=self.account();d=a['driverId'];recovery=self.fleet.rotate_token(d)['developmentToken']
        self.error('INVALID_LOGIN',lambda:self.sign_in())
        self.error('FLEET_AUTH_REQUIRED',lambda:self.fleet.authenticate('Bearer '+a['developmentToken']))
        recovered=self.fleet.recover({'username':'driver.one','password':'New-password-30','recoveryToken':recovery})
        self.assertEqual(recovered['driverId'],d)
        self.error('FLEET_AUTH_REQUIRED',lambda:self.fleet.authenticate('Bearer '+recovery))
        self.error('INVALID_LOGIN',lambda:self.sign_in())
        self.assertEqual(self.sign_in(password='New-password-30')['driverId'],d)
    def test_recovery_cannot_take_another_username_or_active_account(self):
        a=self.account();self.account('driver.two')
        self.error('USERNAME_TAKEN',lambda:self.fleet.recover({'username':'driver.two','password':'New-password-30','recoveryToken':a['developmentToken']}))
        self.error('USERNAME_MISMATCH',lambda:self.fleet.recover({'username':'renamed','password':'New-password-30','recoveryToken':a['developmentToken']}))
        d,r=self.assigned()
        # Admin reset itself is blocked for an active account.
        self.error('ACTIVE_RIDE',lambda:self.fleet.rotate_token(d))
    def test_suspended_account_sign_in_does_not_grant_dispatch(self):
        a=self.register();d=a['driverId'];self.fleet.set_login(d,{'username':'suspended','password':'Test-password-30'})
        self.fleet.approve(d,{'status':'SUSPENDED'});self.sign_in('suspended')
        self.error('DRIVER_NOT_APPROVED',lambda:self.fleet.availability(d,{'online':True}))
    def test_concurrent_same_username_registration_has_one_winner(self):
        def register(_):
            try:self.account();return True
            except FleetError:return False
        with ThreadPoolExecutor(2) as pool:self.assertEqual(sum(pool.map(register,range(2))),1)
    def test_http_logout_and_stale_session_commands(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.service));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def call(path,body=None,token=None):
            req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/v2/fleet/'+path,
                data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+(token or '')})
            try:
                with urllib.request.urlopen(req) as response:return response.status,json.load(response)
            except urllib.error.HTTPError as error:return error.code,json.load(error)
        try:
            code,account=call('auth/register',{'username':'http.driver','password':'Test-password-30','name':'HTTP','vehicle':'Car','plate':'HTTP','category':'ECONOMY'})
            self.assertEqual(code,200);old=account['developmentToken']
            self.assertEqual(call('driver/login-details',token=old)[1]['username'],'http.driver')
            self.assertEqual(call('driver/logout',{},old)[0],200)
            for path,body in [('driver/status',None),('driver/availability',{'online':True}),('driver/location',{'latitude':49.28,'longitude':-123.12}),('driver/logout',{})]:
                self.assertEqual(call(path,body,old)[0],401)
            code,signed=call('auth/login',{'username':'http.driver','password':'Test-password-30'})
            self.assertEqual(code,200);self.assertEqual(signed['driverId'],account['driverId'])
            self.assertEqual(call('driver/status',token=signed['developmentToken'])[0],200)
            ready=self.register();driver=ready['driverId'];token=ready['developmentToken']
            self.fleet.set_login(driver,{'username':'race.driver','password':'Test-password-30'})
            with ThreadPoolExecutor(2) as pool:
                requests=[pool.submit(call,'driver/availability',{'online':True},token),
                          pool.submit(call,'driver/logout',{},token)]
                outcomes=[request.result()[0] for request in requests]
            self.assertIn(outcomes[0],(200,401));self.assertEqual(outcomes[1],200)
            self.assertFalse(self.fleet.status(driver)['online'])
            self.assertEqual(call('driver/status',token=token)[0],401)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
