"""Build 45 integrates authoritative pickup routing and compensation into fleet dispatch."""
import json
import math
from fleet44 import Fleet as Previous, FleetError
from fleet28 import reject

class Fleet(Previous):
    def pickup_route(self, driver, pickup):
        return self.service.pickup_routes.get(driver[0],dict(latitude=driver[7],longitude=driver[8]),pickup)

    def dispatch_route(self, driver, pickup):
        route=self.pickup_route(driver,pickup)
        return route if self.service.pickup_routes.allowed(route) else None

    def _offer_json(self, db, ride, driver, expires, mode, candidate_count=1):
        previous=db.execute('SELECT expires_ms,payload FROM offer_snapshots45 WHERE driver_id=? AND ride_id=?',(driver[0],ride['id'])).fetchone()
        if previous and previous[0]==expires and expires>self.service.clock():return json.loads(previous[1])
        route=self.dispatch_route(driver,ride['draft']['pickup'])
        if route is None:return {}
        result=super()._offer_json(db,ride,driver,expires,mode,candidate_count)
        result.update(pickupDistanceKm=route['distanceMeters']/1000,pickupEtaMin=max(1,math.ceil(route['durationSeconds']/60)),
                      pickupRoute=route,compensation=self.service.compensation.estimate(db,ride,route),
                      locationAgeSeconds=max(0,(self.service.clock()-driver[9])//1000))
        db.execute('DELETE FROM offer_snapshots45 WHERE expires_ms<=? OR (driver_id=? AND ride_id=?)',(self.service.clock(),driver[0],ride['id']))
        db.execute('INSERT INTO offer_snapshots45 VALUES (?,?,?,?)',(driver[0],ride['id'],expires,json.dumps(result)))
        return result

    def prepare_accept45(self,db,ride,driver):
        row=db.execute('SELECT expires_ms,payload FROM offer_snapshots45 WHERE driver_id=? AND ride_id=?',(driver[0],ride['id'])).fetchone()
        # Old API clients still pass through the same server calculation.
        snapshot=json.loads(row[1]) if row and row[0]>self.service.clock() else self._offer_json(db,ride,driver,self.service.clock()+5000,'EXCLUSIVE')
        if not snapshot:reject(409,'PICKUP_UNAVAILABLE','Pickup route is unavailable or exceeds dispatch limits')
        route=snapshot['pickupRoute'];origin=route['origin']
        if self.service.distance_km(driver[7],driver[8],origin['latitude'],origin['longitude'])>.2:
            reject(409,'LOCATION_CHANGED','Driver moved since offer. Decline and wait for a fresh request')
        if not self.service.pickup_routes.allowed(route):reject(409,'PICKUP_UNAVAILABLE','Pickup exceeds current limits')
        ride['offer45']=snapshot
        return route

    def passenger_availability(self,pickup,tier):
        with self.service.connect() as db:
            rows=[r for r in db.execute('SELECT * FROM fleet_drivers') if self.eligible(db,r) and self.category_eligible(db,r[0],tier)]
            choices=[(self.dispatch_route(r,pickup),r) for r in rows]
        choices=[(r,d) for r,d in choices if r]
        if not choices:return None
        route,driver=min(choices,key=lambda x:x[0]['durationSeconds'])
        return dict(available=True,etaMinutes=max(1,math.ceil(route['durationSeconds']/60)),distanceKm=route['distanceMeters']/1000,
                    locationAgeSeconds=max(0,(self.service.clock()-driver[9])//1000),availableDriverCount=len(choices),
                    estimateSource=route['source'],dispatchMode='EXCLUSIVE')

    def active_ride(self,driver_id):
        result=super().active_ride(driver_id)
        if result:
            # Never leak another candidate's offer or a route older than its useful lifetime.
            result.pop('offer45',None)
        return result

    def history(self,driver_id):
        result=super().history(driver_id)
        with self.service.connect() as db:
            for trip in result['trips']:
                rows=db.execute('SELECT payload,start_ms,end_ms FROM engagements45 WHERE ride_id=? AND driver_id=?',(trip['id'],driver_id)).fetchall()
                data=[json.loads(r[0]) for r in rows]
                trip['compensation45']=dict(baseEarningsCents=sum(x['baseCents'] for x in data),bonusCents=sum(x['bonusCents'] for x in data),
                    recordedMeters=sum(x['meters'] for x in data),engagedMs=sum((r[2] or self.service.clock())-r[1] for r in rows),
                    reviewRequired=any(not x['reviewed'] for x in data),payPeriodReconciliation=True)
        return result
