"""Staff delegation and server-side pagination regression tests (development only)."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from server import Service, make_handler
from staff38 import Staff, StaffError

class StaffBuild3839Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.database=str(Path(self.tmp.name)/'test.db')
        self.environment=patch.dict(os.environ, {
            'RIDENOVA_OWNER_USERNAME':'owner_test',
            'RIDENOVA_OWNER_PASSWORD':'a-strong-unique-test-password-12345',
            'RIDENOVA_DEV_ADMIN_TOKEN':'old-admin-token',
        })
        self.environment.start()
        self.service=Service(self.database)
        self.handler=make_handler(self.service)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),self.handler)
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.worker.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.worker.join()
        self.environment.stop();self.tmp.cleanup()
    def call(self,path,token=None,body=None):
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        req=urllib.request.Request(self.base+path,headers=headers,
            data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req,timeout=6) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as error:
            return error.code,json.load(error)
    def owner(self):
        status,data=self.call('/v1/staff/login',body={'username':'owner_test','password':'a-strong-unique-test-password-12345'})
        self.assertEqual(status,200)
        return data['accessToken']
    def test_build39_role_reference_and_ui(self):
        from staff38 import PERMS
        self.assertIn('staff.write',PERMS['OWNER'])
        self.assertNotIn('staff.write',PERMS['OPERATIONS'])
        self.assertNotIn('fleet.write',PERMS['COMPLIANCE'])
        self.assertIn('audit.read',PERMS['COMPLIANCE'])
        with urllib.request.urlopen(self.base+'/admin') as response:
            page=response.read().decode()
        self.assertIn('id="role-preview"',page)
        self.assertIn('updateRolePreview()',page)
        self.assertIn("if(['OWNER','OPERATIONS','DEVELOPMENT'].includes(currentRole))",page)

    def test_owner_bootstrap_and_legacy_token_revocation(self):
        self.assertEqual(self.call('/v1/admin/overview',token='old-admin-token')[0],401)
        self.assertEqual(self.call('/v1/admin/overview',token=self.owner())[0],200)
        self.assertEqual(self.call('/v1/staff/accounts')[0],401)
        self.assertEqual(self.call('/v1/staff/accounts',token=self.owner())[1]['staff'][0]['role'],'OWNER')
    def test_staff_permissions_and_finance_redaction(self):
        owner=self.owner()
        result=self.call('/v1/staff/accounts',token=owner,body={'username':'support_user',
            'password':'a-very-long-support-password','role':'SUPPORT'})
        self.assertEqual(result[0],200)
        login=self.call('/v1/staff/login',body={'username':'support_user','password':'a-very-long-support-password'})
        self.assertEqual(login[0],200)
        support=login[1]['accessToken']
        self.assertEqual(self.call('/v2/fleet/admin/drivers',token=support)[0],403)
        self.assertEqual(self.call('/v1/staff/accounts',token=support)[0],403)
        self.assertEqual(self.call('/v1/admin/support-cases',token=support)[0],200)
        status,summary=self.call('/v1/admin/overview',token=support)
        self.assertEqual(status,200)
        self.assertNotIn('ledger',summary)
        self.assertNotIn('totals',summary)
        self.assertNotIn('fleetDrivers',summary)
    def test_disabled_session_is_revoked(self):
        owner=self.owner()
        status,user=self.call('/v1/staff/accounts',token=owner,body={'username':'operations1',
            'password':'long-unique-operations-pass','role':'OPERATIONS'})
        self.assertEqual(status,200)
        session=self.call('/v1/staff/login',body={'username':'operations1',
            'password':'long-unique-operations-pass'})[1]['accessToken']
        self.assertEqual(self.call('/v2/fleet/admin/drivers',token=session)[0],200)
        self.assertEqual(self.call('/v1/staff/accounts/'+user['id']+'/status',token=owner,body={'active':False})[0],200)
        self.assertEqual(self.call('/v2/fleet/admin/drivers',token=session)[0],401)
        self.assertEqual(self.call('/v1/staff/login',body={'username':'operations1','password':'long-unique-operations-pass'})[0],401)
    def test_logout_revokes_session_and_staff_page_contains_navigation(self):
        token=self.owner()
        self.assertEqual(self.call('/v1/staff/me',token=token)[0],200)
        self.assertEqual(self.call('/v1/staff/logout',token=token,body={})[0],200)
        self.assertEqual(self.call('/v1/staff/me',token=token)[0],401)
        req=urllib.request.Request(self.base+'/admin')
        with urllib.request.urlopen(req) as response:
            page=response.read().decode()
        self.assertIn('Staff accounts & access',page)
        self.assertIn('loadPagedRides',page)
        self.assertIn('Staff username',page)

    def test_audit_and_no_last_owner_lockout(self):
        owner=self.owner()
        accounts=self.call('/v1/staff/accounts',token=owner)[1]['staff']
        self.assertEqual(self.call('/v1/staff/accounts/'+accounts[0]['id']+'/status',token=owner,body={'active':False})[0],409)
        audit=self.call('/v1/staff/audit',token=owner)
        self.assertEqual(audit[0],200)
        self.assertTrue(audit[1]['events'])
    def test_rides_are_server_paginated_and_filtered(self):
        with self.service.connect() as db:
            for i in range(68):
                status='COMPLETED' if i%2 else 'SEARCHING'
                ride={'id':f'rn_paged_{i:03}','status':status,'updatedAtEpochMs':10000+i,
                    'option':{'title':'Economy','breakdown':{'totalCents':1234}},
                    'draft':{'pickup':{'name':'A','address':'Vancouver'},'destination':{'name':'B','address':'Burnaby'}}}
                db.execute('INSERT INTO rides(id,owner,payload) VALUES (?,?,?)',(ride['id'],'test-user',json.dumps(ride)))
        owner=self.owner()
        status,p1=self.call('/v1/admin/rides?page=1&limit=25',token=owner)
        self.assertEqual(status,200)
        self.assertEqual((p1['total'],p1['pages'],len(p1['rides'])),(68,3,25))
        status,p3=self.call('/v1/admin/rides?page=3&limit=25',token=owner)
        self.assertEqual((status,len(p3['rides'])),(200,18))
        self.assertFalse({r['id'] for r in p1['rides']} & {r['id'] for r in p3['rides']})
        _,filtered=self.call('/v1/admin/rides?page=1&limit=25&status=COMPLETED',token=owner)
        self.assertEqual(filtered['total'],34)
        self.assertTrue(all(r['status']=='COMPLETED' for r in filtered['rides']))
        self.assertEqual(self.call('/v1/admin/rides?page=0',token=owner)[0],400)
        self.assertEqual(self.call('/v1/admin/rides?limit=10000',token=owner)[0],400)
        status,matched=self.call('/v1/admin/rides?q=rn_paged_067',token=owner)
        self.assertEqual(status,200)
        self.assertEqual(matched['total'],1)
        self.assertEqual(matched['rides'][0]['id'],'rn_paged_067')
        self.assertEqual(self.call('/v1/admin/rides?q=not%20an%20id',token=owner)[0],400)

if __name__=='__main__':unittest.main()
