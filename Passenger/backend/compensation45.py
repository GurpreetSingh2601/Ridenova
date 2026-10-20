"""CAD-cent compensation. GPS gaps require review; test ledger only, never payouts."""
import calendar
import json
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo
from fleet28 import reject

TZ = ZoneInfo('America/Vancouver')

def rounded(value):
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def period_at(ms):
    d = datetime.fromtimestamp(ms/1000, TZ).date()
    return d.replace(day=1 if d.day <= 15 else 16).isoformat()

def bounds(period):
    try:
        d = date.fromisoformat(period)
        if d.day not in (1,16): raise ValueError()
    except (ValueError, TypeError):
        reject(400,'INVALID_PERIOD','Use YYYY-MM-01 or YYYY-MM-16')
    end = d.replace(day=16) if d.day == 1 else d.replace(day=calendar.monthrange(d.year,d.month)[1])+timedelta(days=1)
    return tuple(int(datetime.combine(x,datetime.min.time(),TZ).timestamp()*1000) for x in (d,end))

class Compensation:
    def __init__(self, service):
        self.s = service
        with service.connect() as db:
            if not service.postgres:
                db.executescript(Path(__file__).with_name('migrations').joinpath('005_trip_compensation.sql').read_text())
            for effective, hourly in [('2024-09-03',2088),('2025-06-01',2143),('2026-06-01',2189)]:
                db.execute('INSERT OR IGNORE INTO pay_policy45 VALUES (?,?,45,?,?)',(effective,hourly,'SYSTEM','BC published minimum'))

    def rates(self, db, ms):
        day = datetime.fromtimestamp(ms/1000,TZ).date().isoformat()
        row = db.execute('SELECT effective_date,hourly_cents,km_cents FROM pay_policy45 WHERE effective_date<=? ORDER BY effective_date DESC LIMIT 1',(day,)).fetchone()
        if not row: reject(409,'PAY_POLICY_MISSING','No compensation policy for this date')
        return dict(effectiveDate=row[0],hourlyCents=row[1],kmCents=row[2])

    def policy(self, actor, body=None):
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if body is not None:
                effective=body.get('effectiveDate'); hourly=body.get('hourlyCents'); km=body.get('kmCents'); reason=body.get('reason','')
                try: day=date.fromisoformat(effective)
                except (ValueError,TypeError): reject(400,'INVALID_POLICY','Valid effective date required')
                if (day<=datetime.fromtimestamp(self.s.clock()/1000,TZ).date() or type(hourly) is not int or not 2189<=hourly<=10000
                    or type(km) is not int or not 45<=km<=200 or not isinstance(reason,str) or not 3<=len(reason.strip())<=300):
                    reject(400,'INVALID_POLICY','Use a future date, valid rates at least current BC floors, and a reason')
                if db.execute('SELECT 1 FROM pay_policy45 WHERE effective_date=?',(effective,)).fetchone():reject(409,'POLICY_EXISTS','Effective-date policy is immutable')
                db.execute('INSERT INTO pay_policy45 VALUES (?,?,?,?,?)',(effective,hourly,km,actor,reason.strip()))
                self.s.operations44.audit(db,actor,'PAY_POLICY_CREATED',effective)
            return {'policies':[dict(zip(('effectiveDate','hourlyCents','kmCents','actor','reason'),r)) for r in db.execute('SELECT * FROM pay_policy45 ORDER BY effective_date')]}

    def zones(self, db, category=None, pickup=None):
        now=self.s.clock()
        rows=db.execute('SELECT id,label,latitude,longitude,radius_km,category,end_ms,bonus_cents,budget_cents,awarded_cents FROM boost_zones WHERE enabled=1 AND start_ms<=? AND end_ms>? ORDER BY bonus_cents DESC,id',(now,now)).fetchall()
        return [dict(zip(('id','label','latitude','longitude','radiusKm','category','endMs','bonusCents'),r[:8])) for r in rows
                if r[8]-r[9]>=r[7] and (category is None or r[5]==category) and
                (pickup is None or self.s.distance_km(pickup['latitude'],pickup['longitude'],r[2],r[3])<=r[4])]

    def estimate(self, db, ride, route):
        rates=self.rates(db,self.s.clock()); trip=ride['draft']['routeEstimate']
        meters=route['distanceMeters']+rounded(trip['distanceKm']*1000)
        seconds=route['durationSeconds']+trip['durationMinutes']*60
        base=ride['option']['breakdown']['driverGrossBeforeCostsCents']
        zones=self.zones(db,ride['option']['tier'],ride['draft']['pickup'])
        bonus=zones[0]['bonusCents'] if zones else 0
        allowance=rounded(Decimal(meters)*rates['kmCents']/1000)
        return dict(baseEarningsCents=base,distanceAllowanceCents=allowance,bonusCents=bonus,
                    estimatedTotalCents=base+allowance+bonus,engagedMeters=meters,engagedSeconds=seconds,
                    earningsPerHourCents=rounded(Decimal(base+bonus)*3600/max(1,seconds)),
                    minimumWageEquivalentCents=rounded(Decimal(seconds)*rates['hourlyCents']/3600),
                    zoneId=zones[0]['id'] if zones else None,bonusStatus='AVAILABLE_AT_ACCEPTANCE',
                    rates=rates,testOnly=True)

    def lifecycle(self, db, ride, event):
        now=self.s.clock(); rid=ride['id']
        if event=='FLEET_ACCEPT':
            driver=ride['fleetDriverId']; eid=rid+':'+driver+':'+str(now)
            if db.execute('SELECT 1 FROM engagements45 WHERE ride_id=? AND end_ms IS NULL',(rid,)).fetchone():return
            snapshot=ride.get('offer45',{}); estimate=snapshot.get('compensation',{})
            p=ride.get('driverPosition',{})
            data=dict(estimate=estimate,pickupRoute={k:v for k,v in snapshot.get('pickupRoute',{}).items() if k not in ('encodedPolyline','origin')},
                      meters=0,lastPoint={**p,'observedAtEpochMs':now},gaps=[],baseCents=0,commissionCents=0,bonusCents=0,tipsCents=0,reviewed=False)
            zone=estimate.get('zoneId'); bonus=estimate.get('bonusCents',0)
            if zone and bonus:
                changed=db.execute('UPDATE boost_zones SET awarded_cents=awarded_cents+? WHERE id=? AND enabled=1 AND start_ms<=? AND end_ms>? AND awarded_cents+?<=budget_cents',
                                   (bonus,zone,now,now,bonus)).rowcount
                if changed:
                    db.execute("INSERT INTO boost_reservations45 VALUES (?,?,?,'RESERVED')",(eid,zone,bonus));data['reservedBonusCents']=bonus
                else:reject(409,'BOOST_CHANGED','Bonus availability changed. Refresh the offer before accepting')
            db.execute('INSERT INTO engagements45 VALUES (?,?,?,?,NULL,?)',(eid,rid,driver,now,json.dumps(data)))
            ride.pop('offer45',None)
            ride['compensation45']={**estimate,'bonusStatus':'RESERVED' if bonus else 'NONE'}
            db.execute('UPDATE rides SET payload=? WHERE id=?',(json.dumps(ride),rid))
        elif event in ('FLEET_COMPLETE','FLEET_CANCEL','FLEET_NO_SHOW','RIDER_CANCELLED','ADMIN_REASSIGN'):
            rows=db.execute('SELECT id,driver_id,start_ms,payload FROM engagements45 WHERE ride_id=? AND end_ms IS NULL',(rid,)).fetchall()
            for eid,driver,start,payload in rows:
                data=json.loads(payload);data['endReason']=event
                if now-data['lastPoint'].get('observedAtEpochMs',start)>120000:data['gaps'].append('FINAL_GPS_GAP')
                reservation=db.execute('SELECT zone_id,bonus_cents,status FROM boost_reservations45 WHERE engagement_id=?',(eid,)).fetchone()
                if event=='FLEET_COMPLETE':
                    data['baseCents']=ride['option']['breakdown']['driverGrossBeforeCostsCents']
                    data['commissionCents']=ride['option']['breakdown']['platformCommissionCents']
                    if reservation and reservation[2]=='RESERVED':
                        data['bonusCents']=reservation[1]
                        db.execute("UPDATE boost_reservations45 SET status='AWARDED' WHERE engagement_id=?",(eid,))
                        db.execute('INSERT OR IGNORE INTO boost_awards VALUES (?,?,?,?,?)',(rid,reservation[0],driver,reservation[1],now))
                        self.s.finance._ledger(db,'boost:'+rid,rid,driver,'PLATFORM_FUNDED_BOOST',reservation[1])
                elif reservation and reservation[2]=='RESERVED':
                    db.execute('UPDATE boost_zones SET awarded_cents=awarded_cents-? WHERE id=?',(reservation[1],reservation[0]))
                    db.execute("UPDATE boost_reservations45 SET status='RELEASED' WHERE engagement_id=?",(eid,))
                # GPS chord sums are observations, never asserted to be an exact road odometer.
                # Every closed assignment requires verified distance before period finalization.
                data.pop('lastPoint',None)
                data['gaps']=sorted(set(data['gaps']+['DISTANCE_VERIFICATION_REQUIRED']))
                db.execute('UPDATE engagements45 SET end_ms=?,payload=? WHERE id=?',(now,json.dumps(data),eid))

    def gps(self, db, ride, driver, point):
        row=db.execute('SELECT id,start_ms,payload FROM engagements45 WHERE ride_id=? AND driver_id=? AND end_ms IS NULL',(ride['id'],driver)).fetchone()
        if not row:return
        data=json.loads(row[2]); last=data['lastPoint']; at=point['observedAtEpochMs']; elapsed=at-last.get('observedAtEpochMs',row[1])
        if elapsed<=0:return
        if point.get('quality')!='RELIABLE':
            data['gaps']=sorted(set(data['gaps']+['UNCERTAIN_GPS']))
        else:
            distance=self.s.distance_km(last['latitude'],last['longitude'],point['latitude'],point['longitude'])*1000
            if elapsed>120000 or distance/(elapsed/1000)>55:
                data['gaps']=sorted(set(data['gaps']+['GPS_GAP_OR_JUMP']))
            else:data['meters']+=rounded(distance)
            data['lastPoint']=point
        db.execute('UPDATE engagements45 SET payload=? WHERE id=?',(json.dumps(data),row[0]))

    def allocations(self, db, row):
        eid,rid,driver,start,end,payload=row;data=json.loads(payload)
        stop=end if end is not None else self.s.clock()
        cursor=start; parts=[]; total=max(1,stop-start)
        while cursor<stop:
            period=period_at(cursor); _,boundary=bounds(period)
            # Split at rate-effective local midnights too.
            following=db.execute('SELECT effective_date FROM pay_policy45 WHERE effective_date>? ORDER BY effective_date LIMIT 1',(datetime.fromtimestamp(cursor/1000,TZ).date().isoformat(),)).fetchone()
            if following:boundary=min(boundary,int(datetime.combine(date.fromisoformat(following[0]),datetime.min.time(),TZ).timestamp()*1000))
            finish=min(stop,boundary);rates=self.rates(db,cursor);ms=finish-cursor
            parts.append(dict(period=period,startMs=cursor,endMs=finish,engagedMs=ms,rates=rates))
            cursor=finish
        if not parts:parts=[dict(period=period_at(start),startMs=start,endMs=stop,engagedMs=0,rates=self.rates(db,start))]
        # Allocate integers with exact conservation; boundary distance is explicitly subject to review.
        for key,value in [('meters',data['meters']),('baseCents',data['baseCents']),('commissionCents',data.get('commissionCents',0)),('bonusCents',data['bonusCents']),('tipsCents',data['tipsCents'])]:
            remaining=value
            for i,p in enumerate(parts):
                p[key]=remaining if i==len(parts)-1 else value*p['engagedMs']//total;remaining-=p[key]
        for p in parts:
            p.update(id=eid,rideId=rid,driverId=driver,active=end is None,reviewRequired=not data.get('reviewed',False),
                     issues=data['gaps'],estimated=data['estimate'],assignmentMeters=data['meters'],boundaryAllocation=len(parts)>1)
            p['minimumNumerator']=p['engagedMs']*p['rates']['hourlyCents']
            p['allowanceNumerator']=p['meters']*p['rates']['kmCents']
        return parts

    def report(self, driver=None, period=None, rid=None, db=None):
        if db is None:
            with self.s.connect() as connection:return self.report(driver,period,rid,connection)
        period=period or period_at(self.s.clock()); start,end=bounds(period)
        query='SELECT * FROM engagements45 WHERE start_ms<? AND (end_ms IS NULL OR end_ms>=?)';args=[end,start]
        if driver:query+=' AND driver_id=?';args.append(driver)
        if rid:query+=' AND ride_id=?';args.append(rid)
        rows=db.execute(query,tuple(args)).fetchall()
        entries=[p for row in rows for p in self.allocations(db,row) if p['period']==period]
        base=sum(p['baseCents'] for p in entries);bonus=sum(p['bonusCents'] for p in entries);tips=sum(p['tipsCents'] for p in entries)
        minimum=rounded(Decimal(sum(p['minimumNumerator'] for p in entries))/3600000)
        allowance=rounded(Decimal(sum(p['allowanceNumerator'] for p in entries))/1000)
        # All-driver dashboards must sum individual shortfalls; one driver's earnings cannot offset another's.
        drivers={p['driverId'] for p in entries}
        allowance=sum(rounded(Decimal(sum(p['allowanceNumerator'] for p in entries if p['driverId']==d))/1000) for d in drivers)
        topup=sum(max(0,rounded(Decimal(sum(p['minimumNumerator'] for p in entries if p['driverId']==d))/3600000)-sum(p['baseCents']+p['bonusCents'] for p in entries if p['driverId']==d)) for d in drivers)
        result=dict(period=period,startMs=start,endMs=end,entries=entries,baseEarningsCents=base,bonusCents=bonus,tipsCents=tips,
                    minimumWageCents=minimum,distanceAllowanceCents=allowance,topUpCents=topup,totalCents=base+bonus+tips+allowance+topup,
                    engagedMs=sum(p['engagedMs'] for p in entries),meters=sum(p['meters'] for p in entries),
                    reviewRequired=any(p['reviewRequired'] or p['active'] for p in entries),testOnly=True,payoutsEnabled=False)
        result['platformCommissionCents']=sum(p['commissionCents'] for p in entries)
        result['platformNetBeforeOtherCostsCents']=result['platformCommissionCents']-allowance-topup-bonus
        result['filteredInvestigation']=bool(rid)
        if driver:
            saved=db.execute('SELECT payload FROM pay_periods45 WHERE driver_id=? AND period=?',(driver,period)).fetchone()
            result['finalized']=json.loads(saved[0]) if saved else None
        return result

    def review(self, actor, body):
        eid=body.get('engagementId');meters=body.get('verifiedMeters');reason=body.get('reason','')
        if type(meters) is not int or not 0<=meters<=2000000 or not isinstance(reason,str) or not 10<=len(reason.strip())<=500:
            reject(400,'INVALID_REVIEW','Verified actual metres and an evidence-based reason (10–500 characters) required')
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM engagements45 WHERE id=?',(eid,)).fetchone()
            if not row:reject(404,'ENGAGEMENT_NOT_FOUND','Assignment not found')
            if row[4] is None:reject(409,'TRIP_ACTIVE','Finish assignment before reviewing')
            parts=self.allocations(db,row)
            if any(db.execute('SELECT 1 FROM pay_periods45 WHERE driver_id=? AND period=?',(row[2],p['period'])).fetchone() for p in parts):reject(409,'PERIOD_FINALIZED','Finalized records require a separate payroll correction; cannot rewrite history')
            data=json.loads(row[5]);data.update(meters=meters,reviewed=True,review=dict(actor=actor,reason=reason.strip(),atMs=self.s.clock(),previousMeters=data['meters']))
            db.execute('UPDATE engagements45 SET payload=? WHERE id=?',(json.dumps(data),eid))
            self.s.operations44.audit(db,actor,'COMPENSATION_DISTANCE_REVIEW',json.dumps(dict(engagementId=eid,verifiedMeters=meters,reason=reason)))
        return {'reviewed':True,'boundaryAllocation':'Time-proportional where a trip crosses a policy/pay-period boundary'}

    def finalize(self, actor, driver, period):
        with self.s.connect() as db:
            db.execute('BEGIN IMMEDIATE');report=self.report(driver,period,db=db)
            if report.get('finalized'):return report['finalized']
            if not report['entries']:reject(409,'EMPTY_PERIOD','No assignments for this driver and period')
            if self.s.clock()<report['endMs'] or report['reviewRequired']:reject(409,'PERIOD_NOT_READY','Period must be closed and all assignments reviewed')
            result={k:v for k,v in report.items() if k not in ('entries','finalized')};result.update(actor=actor,finalizedAtMs=self.s.clock())
            db.execute('INSERT INTO pay_periods45 VALUES (?,?,?)',(driver,period,json.dumps(result)))
            for kind,amount in [('DISTANCE_ALLOWANCE',report['distanceAllowanceCents']),('MINIMUM_WAGE_TOPUP',report['topUpCents'])]:
                self.s.finance._ledger(db,'pay45:'+driver+':'+period+':'+kind,'period:'+period,driver,kind,amount)
            self.s.operations44.audit(db,actor,'PAY_PERIOD_FINALIZED',driver+':'+period)
            return result
