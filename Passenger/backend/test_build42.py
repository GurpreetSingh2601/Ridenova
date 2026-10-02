import json
import io
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from server import Service
from finance42 import FinanceError
from sandbox_stripe import StripeTest
from settings import Settings
from wsgi import create_app


class FakeStripe:
    enabled = True
    def __init__(self): self.requests = []; self.intent_status = 'requires_capture'
    def call(self, method, path, fields=None, idempotency=None):
        self.requests.append((method,path,idempotency))
        if path == '/v1/customers': return {'id':'cus_test42','livemode':False}
        if path == '/v1/checkout/sessions': return {'id':'cs_test_abcdef','customer':'cus_test42','mode':'setup','url':'https://checkout.stripe.com/c/test42','livemode':False}
        if path.startswith('/v1/checkout/sessions/'): return {'customer':'cus_test42','status':'complete','setup_intent':'seti_test42','livemode':False}
        if path.startswith('/v1/setup_intents/'): return {'customer':'cus_test42','status':'succeeded','payment_method':'pm_test42','livemode':False}
        if path.startswith('/v1/payment_methods/'): return {'customer':'cus_test42','type':'card','card':{'brand':'visa','last4':'4242','exp_month':12,'exp_year':2031},'livemode':False}
        if path == '/v1/payment_intents': return {'id':'pi_test42','customer':'cus_test42','payment_method':'pm_test42','amount':fields['amount'],'currency':'cad','status':self.intent_status,'livemode':False}
        if path.endswith('/capture'): self.intent_status='succeeded';return {'id':'pi_test42','status':'succeeded','amount_received':6053,'livemode':False}
        if path.startswith('/v1/payment_intents/'): return {'id':'pi_test42','status':self.intent_status,'amount':6053,'amount_received':6053,'currency':'cad','livemode':False}
        if path == '/v1/refunds': return {'id':'re_test42','payment_intent':'pi_test42','amount':fields['amount'],'status':'succeeded','livemode':False}
        if path.startswith('/v1/refunds/'): return {'id':'re_test42','payment_intent':'pi_test42','amount':200,'status':'succeeded','livemode':False}
        raise AssertionError(path)


class Finance42Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.service=Service(str(Path(self.tmp.name)/'finance.sqlite'))
        self.fake=FakeStripe(); self.service.finance.provider=self.fake
        self.service.settings=type('S',(),{'environment':'staging','origin':'https://staging.example'})()
        self.owner='test-owner'
        with self.service.connect() as db:
            db.execute('INSERT INTO passengers(id,phone,created_ms,updated_ms) VALUES (?,?,?,?)',(self.owner,'+16045550123',1,1))

    def ride(self, rid, driver='drv42'):
        return {'id':rid,'status':'COMPLETED','requestedAtEpochMs':10000,'fleetDriverId':driver,
                'draft':{'pickup':{'latitude':49.28,'longitude':-123.12}},
                'payment':{'methodId':'pm_test42'},
                'option':{'tier':'ECONOMY','breakdown':{'subtotalCents':5765,'gstCents':288,'totalCents':6053,'platformCommissionCents':1730,'driverGrossBeforeCostsCents':4035}}}

    def test_test_card_setup_ownership_authorize_capture_refund_reconcile(self):
        start=self.service.finance.start_setup(self.owner)
        with self.assertRaises(FinanceError): self.service.finance.sync_setup('other',{'sessionId':start['sessionId']})
        methods=self.service.finance.sync_setup(self.owner,{'sessionId':start['sessionId']})['paymentMethods']
        self.assertEqual([m for m in methods if m['id']=='pm_test42'][0]['developmentOnly'],False)
        with self.service.connect() as db: db.execute('INSERT INTO rides VALUES (?,?,?)',('ride42',self.owner,json.dumps(self.ride('ride42'))))
        auth=self.service.finance.authorize(self.owner,'ride42')
        self.assertEqual(auth['status'],'requires_capture')
        self.assertEqual(self.service.finance.authorize(self.owner,'ride42'),auth)
        self.assertEqual(self.fake.requests[-1][2], 'rn42:authorize:ride42')
        self.assertEqual(self.service.finance.capture('ride42')['status'],'succeeded')
        self.service.finance.capture('ride42')
        self.service.finance.refund('ride42','refund_test_1',200)
        self.service.finance.refund('ride42','refund_test_1',200)
        with self.assertRaises(FinanceError): self.service.finance.refund('ride42','refund_test_1',300)
        self.assertTrue(self.service.finance.reconcile('ride42')['reconciled'])
        # Recover when Stripe committed but the local response/ledger write was lost.
        with self.service.connect() as db:
            db.execute('UPDATE sandbox_payments SET status=? WHERE ride_id=?',('requires_capture','ride42'))
            db.execute('UPDATE sandbox_refunds SET status=? WHERE ride_id=?',('pending','ride42'))
            db.execute('DELETE FROM finance_entries')
        self.assertTrue(self.service.finance.reconcile('ride42',settle=True)['reconciled'])
        self.assertTrue(self.service.finance.reconcile('ride42',settle=True)['reconciled'])
        summary=self.service.finance.summary()
        self.assertCountEqual([(e['kind'],e['amountCents']) for e in summary['entries']], [('PASSENGER_REFUND',-200),('PASSENGER_CAPTURE',6053)])

    def test_budget_cap_and_duplicate_completion(self):
        finance=self.service.finance
        zone=finance.create_zone({'label':'Downtown','latitude':49.28,'longitude':-123.12,'radiusKm':2,
                                  'category':'ECONOMY','startMs':1000,'endMs':20000,'bonusCents':200,'budgetCents':200})
        finance.toggle_zone(zone['id'],True)
        for rid in ('ride_a','ride_b'):
            with self.service.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                finance.completed(db,self.ride(rid))
                finance.completed(db,self.ride(rid))
        with self.service.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM boost_awards').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT awarded_cents FROM boost_zones').fetchone()[0],200)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM finance_entries WHERE kind='PLATFORM_FUNDED_BOOST'").fetchone()[0],1)
        self.assertEqual(sum(e['amountCents'] for e in finance.summary()['entries'] if e['kind']=='PLATFORM_FUNDED_BOOST'),200)
        self.assertEqual(finance.summary()['provisionalDriverBalances'],
                         [{'driverId':'drv42','grossBeforeCostsCents':8270,'payoutEligible':False}])

    def test_finance_summary_serializes_postgres_decimal_balance(self):
        class Cursor:
            def __init__(self, rows): self.rows=rows
            def fetchall(self): return self.rows
        class Connection:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def execute(self, query):
                return Cursor([('drv42', Decimal('4235'))] if 'GROUP BY driver_id' in query else [])
        with patch.object(self.service, 'connect', return_value=Connection()):
            summary=self.service.finance.summary()
        self.assertEqual(summary['provisionalDriverBalances'][0]['grossBeforeCostsCents'],4235)
        json.dumps(summary,allow_nan=False)

    def test_live_secret_fails_closed(self):
        with self.assertRaises(ValueError): StripeTest('sk_live_unsafe')

    def test_rate_checks_share_one_database_connection(self):
        import sys
        import types
        from operations import allow_requests
        class Cursor:
            def __init__(self, count): self.count=count
            def fetchone(self): return (self.count,)
        class Connection:
            def __init__(self): self.calls=0
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def execute(self,*_): self.calls+=1; return Cursor(self.calls)
        conn=Connection(); created=[]
        def connect(*_,**__): created.append(conn); return conn
        with patch.dict(sys.modules, {'psycopg':types.SimpleNamespace(connect=connect)}):
            self.assertFalse(allow_requests('unused','x'*40,[('api:global',10,60),('api:owner',1,60),('auth',10,60)]))
        self.assertEqual((len(created),conn.calls),(1,3))

    def test_admin_finance_permissions_and_passenger_auth(self):
        from staff38 import Staff
        staff=Staff(self.service.database)
        with staff.connect() as db:
            staff._create(db,'owner42','a-very-long-password-42','OWNER','fixture')
            staff._create(db,'finance42','a-very-long-password-42','FINANCE','fixture')
            staff._create(db,'support42','a-very-long-password-42','SUPPORT','fixture')
        app_settings=Settings('staging',self.service.database,'https://staging.example',{},(), 'a'*40)
        with patch('migrate.check'), patch('operations.allow_requests',return_value=True):
            app=create_app(app_settings)
            def call(path,token=None,body=None):
                data=json.dumps(body).encode() if body is not None else b''
                env={'PATH_INFO':path,'REQUEST_METHOD':'POST' if body is not None else 'GET',
                     'CONTENT_LENGTH':str(len(data)),'CONTENT_TYPE':'application/json','wsgi.input':io.BytesIO(data),
                     'wsgi.url_scheme':'https','HTTP_HOST':'staging.example'}
                if token:env['HTTP_AUTHORIZATION']='Bearer '+token
                out={}
                def start(status, headers):out['status']=int(status.split()[0])
                out['body']=b''.join(app(env,start))
                return out
            tokens={role:staff.login({'username':role+'42','password':'a-very-long-password-42'})['accessToken'] for role in ('owner','finance','support')}
            self.assertEqual(call('/v1/admin/finance/summary')['status'],401)
            self.assertEqual(call('/v1/admin/finance/summary',tokens['support'])['status'],403)
            self.assertEqual(call('/v1/admin/finance/summary',tokens['finance'])['status'],200)
            self.assertEqual(call('/v1/admin/finance/zones',tokens['finance'],{})['status'],403)
            self.assertEqual(call('/v1/admin/finance/zones',tokens['owner'],{'label':'bad'})['status'],400)
            self.assertEqual(call('/v1/passenger/payment-methods/setup',body={})['status'],401)

if __name__=='__main__': unittest.main()
