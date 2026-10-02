"""Build 42 test-only payments, immutable money events and bounded driver bonuses."""
import json
import math
import os
import re
import secrets
from sandbox_stripe import StripeTest, ProviderError


class FinanceError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def reject(status, code, message):
    raise FinanceError(status, code, message)


class Finance:
    def __init__(self, service, provider=None):
        self.service = service
        self.provider = provider or StripeTest()
        if service.postgres:
            return
        with service.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sandbox_customers(passenger_id TEXT PRIMARY KEY,provider_customer_id TEXT NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS sandbox_setups(session_id TEXT PRIMARY KEY,passenger_id TEXT NOT NULL,created_ms INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sandbox_cards(payment_method_id TEXT PRIMARY KEY,passenger_id TEXT NOT NULL,provider_customer_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sandbox_payments(ride_id TEXT PRIMARY KEY,passenger_id TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>0),provider_intent_id TEXT UNIQUE,status TEXT NOT NULL,updated_ms INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sandbox_refunds(ride_id TEXT NOT NULL,request_key TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>0),provider_refund_id TEXT UNIQUE,status TEXT NOT NULL,created_ms INTEGER NOT NULL,PRIMARY KEY(ride_id,request_key));
                CREATE TABLE IF NOT EXISTS finance_entries(entry_key TEXT PRIMARY KEY,ride_id TEXT NOT NULL,driver_id TEXT,kind TEXT NOT NULL,amount_cents INTEGER NOT NULL,at_ms INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS finance_entries_ride ON finance_entries(ride_id,at_ms);
                CREATE TABLE IF NOT EXISTS boost_zones(id TEXT PRIMARY KEY,label TEXT NOT NULL,latitude REAL NOT NULL,longitude REAL NOT NULL,radius_km REAL NOT NULL,category TEXT NOT NULL,start_ms INTEGER NOT NULL,end_ms INTEGER NOT NULL,bonus_cents INTEGER NOT NULL,budget_cents INTEGER NOT NULL,awarded_cents INTEGER NOT NULL DEFAULT 0,enabled INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS boost_awards(ride_id TEXT PRIMARY KEY,zone_id TEXT NOT NULL,driver_id TEXT NOT NULL,bonus_cents INTEGER NOT NULL,awarded_ms INTEGER NOT NULL);
            ''')

    def available(self):
        return bool(self.provider.enabled and getattr(self.service, 'settings', None) and
                    self.service.settings.environment == 'staging')

    def require_test(self):
        if not self.available():
            reject(503, 'SANDBOX_UNAVAILABLE', 'Stripe test payments are not configured for this staging service')

    def start_setup(self, owner):
        self.require_test()
        with self.service.connect() as db:
            row = db.execute('SELECT provider_customer_id FROM sandbox_customers WHERE passenger_id=?', (owner,)).fetchone()
        if row:
            customer = row[0]
        else:
            created = self.provider.call('POST', '/v1/customers',
                                         {'metadata[ridenova_passenger_id]': owner}, 'rn42:customer:' + owner)
            customer = created['id']
            with self.service.connect() as db:
                db.execute('INSERT OR IGNORE INTO sandbox_customers VALUES (?,?)', (owner, customer))
                customer = db.execute('SELECT provider_customer_id FROM sandbox_customers WHERE passenger_id=?', (owner,)).fetchone()[0]
        origin = self.service.settings.origin
        session = self.provider.call('POST', '/v1/checkout/sessions', {
            'mode': 'setup', 'customer': customer, 'payment_method_types[0]': 'card',
            'success_url': origin + '/payments/return?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': origin + '/payments/return?cancelled=1',
            'metadata[ridenova_passenger_id]': owner,
        }, 'rn42:setup:' + owner + ':' + secrets.token_hex(12))
        if session.get('mode') != 'setup' or session.get('customer') != customer or not session.get('url', '').startswith('https://checkout.stripe.com/'):
            reject(502, 'PROVIDER_RESPONSE', 'Stripe did not return a valid test setup session')
        with self.service.connect() as db:
            db.execute('INSERT INTO sandbox_setups VALUES (?,?,?)', (session['id'], owner, self.service.clock()))
        return {'sessionId': session['id'], 'url': session['url'], 'testOnly': True}

    def sync_setup(self, owner, body):
        self.require_test()
        sid = body.get('sessionId')
        if not isinstance(sid, str) or not re.fullmatch(r'cs_test_[a-zA-Z0-9_]{5,120}', sid):
            reject(400, 'INVALID_SESSION', 'Invalid test setup session')
        with self.service.connect() as db:
            row = db.execute('SELECT c.provider_customer_id FROM sandbox_setups s JOIN sandbox_customers c ON c.passenger_id=s.passenger_id WHERE s.session_id=? AND s.passenger_id=?', (sid, owner)).fetchone()
        if not row:
            reject(404, 'SETUP_NOT_FOUND', 'Setup session does not belong to this account')
        session = self.provider.call('GET', '/v1/checkout/sessions/' + sid)
        if session.get('livemode') is not False or session.get('customer') != row[0] or session.get('status') != 'complete':
            reject(409, 'SETUP_INCOMPLETE', 'Finish the card setup on Stripe before returning')
        intent_id = session.get('setup_intent', '')
        if not isinstance(intent_id, str) or not re.fullmatch(r'seti_[a-zA-Z0-9_]+', intent_id):
            reject(502, 'PROVIDER_RESPONSE', 'Missing test setup intent')
        setup = self.provider.call('GET', '/v1/setup_intents/' + intent_id)
        if setup.get('status') != 'succeeded' or setup.get('customer') != row[0]:
            reject(409, 'SETUP_INCOMPLETE', 'Card setup is not complete')
        pm_id = setup.get('payment_method', '')
        if not isinstance(pm_id, str) or not re.fullmatch(r'pm_[a-zA-Z0-9_]+', pm_id):
            reject(502, 'PROVIDER_RESPONSE', 'Invalid test payment method')
        method = self.provider.call('GET', '/v1/payment_methods/' + pm_id)
        card = method.get('card') or {}
        if method.get('customer') != row[0] or method.get('type') != 'card' or not re.fullmatch(r'\d{4}', str(card.get('last4', ''))):
            reject(502, 'PROVIDER_RESPONSE', 'Stripe test card ownership check failed')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM sandbox_cards WHERE payment_method_id=? AND passenger_id=?', (pm_id, owner)).fetchone():
                if db.execute('SELECT COUNT(*) FROM payment_methods WHERE passenger_id=?', (owner,)).fetchone()[0] >= 5:
                    reject(409, 'PAYMENT_METHOD_LIMIT', 'Remove a development card and retry syncing')
                db.execute('INSERT INTO sandbox_cards VALUES (?,?,?)', (pm_id, owner, row[0]))
                db.execute('UPDATE payment_methods SET is_default=0 WHERE passenger_id=?', (owner,))
                db.execute('INSERT INTO payment_methods VALUES (?,?,?,?,?,?,?,?,?)', (
                    pm_id, owner, 'CARD', {'visa':'Visa','mastercard':'Mastercard','amex':'Amex'}.get(card.get('brand'),'Card'),
                    card['last4'], card['exp_month'], card['exp_year'], 1, self.service.clock()))
        return self.service.payment_methods(owner)

    def authorize(self, owner, ride_id):
        self.require_test()
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            ride = self.service.get(owner, ride_id, db)
            if ride['status'] != 'COMPLETED':
                reject(409, 'RIDE_NOT_COMPLETED', 'Test authorization is available after completing the ride')
            pm = ride.get('payment', {}).get('methodId')
            method = db.execute('SELECT provider_customer_id FROM sandbox_cards WHERE payment_method_id=? AND passenger_id=?', (pm, owner)).fetchone()
            if not method:
                reject(409, 'TEST_CARD_REQUIRED', 'Choose a Stripe test card before booking the ride')
            amount = ride['option']['breakdown']['totalCents']
            current = db.execute('SELECT amount_cents,provider_intent_id,status FROM sandbox_payments WHERE ride_id=?', (ride_id,)).fetchone()
            if current and current[0] != amount:
                reject(409, 'FARE_CHANGED', 'Stored fare does not match the payment authorization')
            if not current:
                db.execute('INSERT INTO sandbox_payments VALUES (?,?,?,?,?,?)', (ride_id, owner, amount, None, 'PENDING', self.service.clock()))
        # Fixed provider key per ride protects retries after an ambiguous network response.
        intent = self.provider.call('POST', '/v1/payment_intents', {
            'amount': amount, 'currency': 'cad', 'customer': method[0], 'payment_method': pm,
            'confirm': 'true', 'off_session': 'true', 'capture_method': 'manual',
            'payment_method_types[0]': 'card', 'metadata[ridenova_ride_id]': ride_id,
        }, 'rn42:authorize:' + ride_id)
        if (intent.get('amount') != amount or intent.get('currency') != 'cad' or
                intent.get('customer') != method[0] or intent.get('payment_method') != pm or
                intent.get('livemode') is not False):
            reject(502, 'PROVIDER_RESPONSE', 'Stripe authorization details do not match the ride')
        status = intent.get('status', 'unknown')
        with self.service.connect() as db:
            db.execute('UPDATE sandbox_payments SET provider_intent_id=?,status=?,updated_ms=? WHERE ride_id=? AND passenger_id=?',
                       (intent['id'], status, self.service.clock(), ride_id, owner))
        return {'rideId': ride_id, 'status': status, 'amountCents': amount, 'testOnly': True}

    def capture(self, ride_id):
        self.require_test()
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT passenger_id,amount_cents,provider_intent_id,status FROM sandbox_payments WHERE ride_id=?', (ride_id,)).fetchone()
        if not row or not row[2]:
            reject(409, 'AUTH_REQUIRED', 'Authorize a Stripe test card before capturing')
        if row[3] == 'succeeded':
            return {'rideId': ride_id, 'status': 'succeeded', 'testOnly': True}
        if row[3] != 'requires_capture':
            reject(409, 'AUTH_NOT_READY', 'Stripe authorization is not capturable')
        result = self.provider.call('POST', '/v1/payment_intents/' + row[2] + '/capture', {}, 'rn42:capture:' + ride_id)
        if (result.get('id') != row[2] or result.get('status') != 'succeeded' or
                result.get('amount_received') != row[1] or result.get('livemode') is not False):
            reject(502, 'PROVIDER_RESPONSE', 'Stripe did not confirm test capture')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE sandbox_payments SET status=?,updated_ms=? WHERE ride_id=?', ('succeeded',self.service.clock(),ride_id))
            self._ledger(db, 'capture:'+ride_id, ride_id, None, 'PASSENGER_CAPTURE', row[1])
        return {'rideId': ride_id, 'status': 'succeeded', 'testOnly': True}

    def refund(self, ride_id, key, amount):
        self.require_test()
        if not isinstance(key, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}', key):
            reject(400, 'INVALID_REFUND_KEY', 'Supply a stable refund request key')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT amount_cents,provider_intent_id,status FROM sandbox_payments WHERE ride_id=?', (ride_id,)).fetchone()
            if not row or row[2] != 'succeeded':
                reject(409, 'PAYMENT_NOT_CAPTURED', 'Test payment has not been captured')
            if type(amount) is not int or amount <= 0 or amount > row[0]:
                reject(400, 'INVALID_REFUND', 'Refund amount exceeds the captured fare')
            previous = db.execute('SELECT amount_cents,provider_refund_id,status FROM sandbox_refunds WHERE ride_id=? AND request_key=?', (ride_id,key)).fetchone()
            if previous and previous[0] != amount:
                reject(409, 'REFUND_CONFLICT', 'Refund key is already bound to another amount')
            total = db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM sandbox_refunds WHERE ride_id=?', (ride_id,)).fetchone()[0]
            if not previous and total + amount > row[0]:
                reject(409, 'REFUND_EXCEEDS_CAPTURE', 'Refunds exceed captured amount')
            if not previous:
                db.execute('INSERT INTO sandbox_refunds VALUES (?,?,?,?,?,?)', (ride_id,key,amount,None,'PENDING',self.service.clock()))
        result = self.provider.call('POST', '/v1/refunds', {'payment_intent':row[1],'amount':amount}, 'rn42:refund:' + ride_id + ':' + key)
        if result.get('amount') != amount or result.get('payment_intent') != row[1] or result.get('livemode') is not False:
            reject(502, 'PROVIDER_RESPONSE', 'Stripe refund details do not match')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE sandbox_refunds SET provider_refund_id=?,status=? WHERE ride_id=? AND request_key=?',
                       (result['id'],result['status'],ride_id,key))
            if result['status'] == 'succeeded':
                self._ledger(db, 'refund:'+ride_id+':'+key, ride_id, None, 'PASSENGER_REFUND', -amount)
        return {'rideId':ride_id,'status':result['status'],'amountCents':amount,'testOnly':True}

    def _ledger(self, db, key, ride_id, driver_id, kind, amount):
        db.execute('INSERT OR IGNORE INTO finance_entries VALUES (?,?,?,?,?,?)',
                   (key, ride_id, driver_id, kind, amount, self.service.clock()))

    def completed(self, db, ride):
        """Immutable earnings allocation; boost pays from platform budget only."""
        b = ride['option']['breakdown']
        self._ledger(db,'fare:'+ride['id'],ride['id'],ride.get('fleetDriverId'),'FARE_GROSS',b['totalCents'])
        self._ledger(db,'commission:'+ride['id'],ride['id'],ride.get('fleetDriverId'),'PLATFORM_COMMISSION',b['platformCommissionCents'])
        self._ledger(db,'driver:'+ride['id'],ride['id'],ride.get('fleetDriverId'),'DRIVER_GROSS',b['driverGrossBeforeCostsCents'])
        driver = ride.get('fleetDriverId')
        pickup = ride.get('draft',{}).get('pickup',{})
        lat, lng = pickup.get('latitude'),pickup.get('longitude')
        if not driver or not isinstance(lat,(int,float)) or not isinstance(lng,(int,float)):
            return
        if db.execute('SELECT 1 FROM boost_awards WHERE ride_id=?', (ride['id'],)).fetchone():
            return
        now = self.service.clock()
        category = ride['option']['tier']
        zones = db.execute('SELECT id,latitude,longitude,radius_km,bonus_cents,budget_cents,awarded_cents FROM boost_zones WHERE enabled=1 AND category=? AND start_ms<=? AND end_ms>? ORDER BY bonus_cents DESC,id', (category,ride['requestedAtEpochMs'],ride['requestedAtEpochMs'])).fetchall()
        for zone in zones:
            if self.service.distance_km(lat,lng,zone[1],zone[2]) > zone[3]:
                continue
            # DB-level conditional budget reservation prevents overspend, even across workers.
            count = db.execute('UPDATE boost_zones SET awarded_cents=awarded_cents+? WHERE id=? AND awarded_cents+?<=?', (zone[4],zone[0],zone[4],zone[5])).rowcount
            if count:
                db.execute('INSERT INTO boost_awards VALUES (?,?,?,?,?)', (ride['id'],zone[0],driver,zone[4],now))
                self._ledger(db,'boost:'+ride['id'],ride['id'],driver,'PLATFORM_FUNDED_BOOST',zone[4])
                break

    def zones(self):
        with self.service.connect() as db:
            rows = db.execute('SELECT id,label,latitude,longitude,radius_km,category,start_ms,end_ms,bonus_cents,budget_cents,awarded_cents,enabled FROM boost_zones ORDER BY start_ms DESC LIMIT 100').fetchall()
        return {'zones':[dict(zip(('id','label','latitude','longitude','radiusKm','category','startMs','endMs','bonusCents','budgetCents','awardedCents','enabled'),r)) for r in rows]}

    def create_zone(self, body):
        label=body.get('label',''); lat=body.get('latitude'); lng=body.get('longitude'); radius=body.get('radiusKm'); category=body.get('category'); start=body.get('startMs'); end=body.get('endMs'); bonus=body.get('bonusCents'); budget=body.get('budgetCents')
        if (not isinstance(label,str) or not 2<=len(label.strip())<=80 or
            any(type(x) not in (int,float) or not math.isfinite(x) for x in (lat,lng,radius)) or
            not -90<=lat<=90 or not -180<=lng<=180 or not 0<radius<=5 or
            category not in self.service.config['tiers'] or type(start) is not int or type(end) is not int or
            end<=start or end-start>30*86400000 or type(bonus) is not int or not 100<=bonus<=5000 or
            type(budget) is not int or bonus>budget or budget>1000000):
            reject(400,'INVALID_BOOST_ZONE','Use valid coordinates, category, dates and capped CAD cents')
        zone='bz_'+secrets.token_hex(10)
        with self.service.connect() as db:
            db.execute('INSERT INTO boost_zones VALUES (?,?,?,?,?,?,?,?,?,?,0,0)', (zone,label.strip(),lat,lng,radius,category,start,end,bonus,budget))
        return {'id':zone,'enabled':False,'platformFunded':True}

    def toggle_zone(self, zone_id, enabled):
        if type(enabled) is not bool:
            reject(400,'INVALID_BOOST_ZONE','enabled must be true or false')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT budget_cents,awarded_cents FROM boost_zones WHERE id=?', (zone_id,)).fetchone()
            if not row: reject(404,'ZONE_NOT_FOUND','Unknown boost zone')
            if enabled and row[1]>=row[0]: reject(409,'BUDGET_EXHAUSTED','Boost budget is exhausted')
            db.execute('UPDATE boost_zones SET enabled=? WHERE id=?', (int(enabled),zone_id))
        return {'id':zone_id,'enabled':enabled}

    def summary(self):
        with self.service.connect() as db:
            entries=db.execute('SELECT entry_key,ride_id,driver_id,kind,amount_cents,at_ms FROM finance_entries ORDER BY at_ms DESC LIMIT 200').fetchall()
            payments=db.execute('SELECT ride_id,amount_cents,status FROM sandbox_payments ORDER BY updated_ms DESC LIMIT 100').fetchall()
            refunds=db.execute('SELECT ride_id,request_key,amount_cents,status FROM sandbox_refunds ORDER BY created_ms DESC LIMIT 100').fetchall()
            balances=db.execute("SELECT driver_id,COALESCE(SUM(amount_cents),0) FROM finance_entries WHERE driver_id IS NOT NULL AND kind IN ('DRIVER_GROSS','PLATFORM_FUNDED_BOOST') GROUP BY driver_id ORDER BY driver_id LIMIT 200").fetchall()
        return {'testOnly':True,'providerConfigured':self.available(),
                'entries':[dict(zip(('key','rideId','driverId','kind','amountCents','atMs'),e)) for e in entries],
                'payments':[dict(zip(('rideId','amountCents','status'),p)) for p in payments],
                'refunds':[dict(zip(('rideId','requestKey','amountCents','status'),r)) for r in refunds],
                # PostgreSQL SUM(BIGINT) returns NUMERIC (Decimal), which JSON cannot encode.
                # Cents are integral throughout the ledger; normalize at the API boundary.
                'provisionalDriverBalances':[{'driverId':d,'grossBeforeCostsCents':int(amount),'payoutEligible':False} for d,amount in balances],
                'payoutsEnabled':False}

    def reconcile(self, ride_id, settle=False):
        self.require_test()
        with self.service.connect() as db:
            payment=db.execute('SELECT amount_cents,provider_intent_id,status FROM sandbox_payments WHERE ride_id=?',(ride_id,)).fetchone()
            refunds=db.execute('SELECT request_key,amount_cents,provider_refund_id,status FROM sandbox_refunds WHERE ride_id=?',(ride_id,)).fetchall()
            entries=db.execute('SELECT kind,amount_cents FROM finance_entries WHERE ride_id=?',(ride_id,)).fetchall()
        if not payment:
            reject(404,'PAYMENT_NOT_FOUND','No Stripe test payment for this ride')
        actual=None
        if payment[1]:
            actual=self.provider.call('GET','/v1/payment_intents/'+payment[1])
        issues=[]
        if actual and (actual.get('amount') != payment[0] or actual.get('currency') != 'cad'):
            issues.append('PAYMENT_AMOUNT_MISMATCH')
        elif actual and actual.get('status') != payment[2]:
            if settle and actual.get('status') == 'succeeded' and actual.get('amount_received') == payment[0]:
                with self.service.connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    db.execute('UPDATE sandbox_payments SET status=?,updated_ms=? WHERE ride_id=? AND provider_intent_id=?',
                               ('succeeded',self.service.clock(),ride_id,payment[1]))
                    self._ledger(db,'capture:'+ride_id,ride_id,None,'PASSENGER_CAPTURE',payment[0])
                payment=(payment[0],payment[1],'succeeded')
            else: issues.append('PAYMENT_STATUS_MISMATCH')
        if settle and actual and actual.get('status') == 'succeeded' and actual.get('amount_received') == payment[0] and not issues:
            with self.service.connect() as db:
                self._ledger(db,'capture:'+ride_id,ride_id,None,'PASSENGER_CAPTURE',payment[0])
        for key,amount,provider_id,status in refunds:
            if provider_id:
                actual_refund=self.provider.call('GET','/v1/refunds/'+provider_id)
                if actual_refund.get('amount') != amount or actual_refund.get('payment_intent') != payment[1]:
                    issues.append('REFUND_AMOUNT_MISMATCH:'+key)
                elif actual_refund.get('status') != status:
                    if settle and actual_refund.get('status') == 'succeeded':
                        with self.service.connect() as db:
                            db.execute('BEGIN IMMEDIATE')
                            db.execute('UPDATE sandbox_refunds SET status=? WHERE ride_id=? AND request_key=? AND provider_refund_id=?',
                                       ('succeeded',ride_id,key,provider_id))
                            self._ledger(db,'refund:'+ride_id+':'+key,ride_id,None,'PASSENGER_REFUND',-amount)
                    else: issues.append('REFUND_STATUS_MISMATCH:'+key)
                if settle and actual_refund.get('status') == 'succeeded' and actual_refund.get('amount') == amount and actual_refund.get('payment_intent') == payment[1]:
                    with self.service.connect() as db:
                        self._ledger(db,'refund:'+ride_id+':'+key,ride_id,None,'PASSENGER_REFUND',-amount)
            else:
                issues.append('REFUND_PENDING:'+key)
        if payment[2]=='succeeded' and not settle and sum(a for k,a in entries if k=='PASSENGER_CAPTURE')!=payment[0]:
            issues.append('CAPTURE_LEDGER_MISMATCH')
        return {'rideId':ride_id,'providerStatus':actual.get('status') if actual else None,
                'localStatus':payment[2],'issues':issues,'reconciled':not issues,'testOnly':True}
