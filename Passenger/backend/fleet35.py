"""Build 40 fleet eligibility, shared Trip Radar and dispatch reliability.

Trip Radar is deliberately bounded: only approved, document-ready drivers with
fresh GPS, the requested eligibility, and a pickup distance <= 4 km participate.
The first transactionally valid claim wins. Unclaimed radar rides fall back to
the normal exclusive 20-second offer queue after twelve seconds.
"""
import json

from fleet33 import Fleet as PreviousFleet, FleetError, reject


RADAR_RADIUS_KM = 4.0
RADAR_WINDOW_MS = 12_000
EXCLUSIVE_WINDOW_MS = 20_000
EXPLICIT_DECLINE_UNTIL_MS = 9_223_372_036_854_775_807


class Fleet(PreviousFleet):
    def __init__(self, service):
        super().__init__(service)
        if service.postgres:
            return
        with service.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS fleet_driver_eligibility (
                driver_id TEXT NOT NULL, category TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'ADMIN', updated_ms INTEGER NOT NULL,
                PRIMARY KEY(driver_id, category));
            CREATE TABLE IF NOT EXISTS fleet_radar (
                ride_id TEXT PRIMARY KEY, expires_ms INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN', created_ms INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS fleet_radar_candidates (
                ride_id TEXT NOT NULL, driver_id TEXT NOT NULL, distance_km REAL NOT NULL,
                PRIMARY KEY(ride_id, driver_id));
            CREATE INDEX IF NOT EXISTS fleet_radar_driver
                ON fleet_radar_candidates(driver_id, ride_id);
            """)
            now = service.clock()
            for driver_id, category in db.execute('SELECT id,category FROM fleet_drivers').fetchall():
                db.execute('INSERT OR IGNORE INTO fleet_driver_eligibility VALUES (?,?,?,?)',
                           (driver_id, 'ECONOMY', 'MIGRATED', now))
                if category in service.config['tiers']:
                    db.execute('INSERT OR IGNORE INTO fleet_driver_eligibility VALUES (?,?,?,?)',
                               (driver_id, category, 'MIGRATED', now))

    def register_account(self, body):
        # Drivers apply once. Ride categories are assigned by operations after
        # vehicle/document review; self-selecting Comfort/XL is not authoritative.
        request = dict(body)
        request['category'] = 'ECONOMY'
        result = super().register_account(request)
        with self.service.connect() as db:
            db.execute('INSERT OR REPLACE INTO fleet_driver_eligibility VALUES (?,?,?,?)',
                       (result['driverId'], 'ECONOMY', 'SIGNUP_DEFAULT', self.service.clock()))
        result.update(eligibleCategories=['ECONOMY'], eligibilityReview='PENDING_ADMIN_REVIEW')
        return result

    def register(self, body):
        """Keep the token-only development path compatible while migrating eligibility."""
        result = super().register(body)
        category = body.get('category', 'ECONOMY')
        with self.service.connect() as db:
            db.execute('INSERT OR REPLACE INTO fleet_driver_eligibility VALUES (?,?,?,?)',
                       (result['driverId'], category, 'LEGACY_REGISTRATION', self.service.clock()))
        return result

    def categories(self, db, driver_id):
        rows = db.execute('SELECT category FROM fleet_driver_eligibility WHERE driver_id=? ORDER BY category',
                          (driver_id,)).fetchall()
        return [row[0] for row in rows] or ['ECONOMY']

    def category_eligible(self, db, driver_id, category):
        return bool(db.execute('SELECT 1 FROM fleet_driver_eligibility WHERE driver_id=? AND category=?',
                               (driver_id, category)).fetchone())

    def status(self, driver_id):
        result = super().status(driver_id)
        with self.service.connect() as db:
            result['eligibleCategories'] = self.categories(db, driver_id)
            rating = db.execute("SELECT COUNT(*),COALESCE(AVG(stars),0) FROM ride_feedback "
                                "WHERE target_id=? AND author_role='PASSENGER'", (driver_id,)).fetchone()
            result['ratingCount'] = rating[0]
            result['serviceRating'] = round(float(rating[1]), 2) if rating[0] else None
            result['comfortRatingQualified'] = bool(rating[0] >= 10 and rating[1] >= 4.85)
        result['category'] = ' · '.join(result['eligibleCategories'])
        return result

    def set_eligibility(self, driver_id, body):
        categories = body.get('categories')
        valid = set(self.service.config['tiers'])
        if (not isinstance(categories, list) or not categories or
                any(not isinstance(item, str) or item not in valid for item in categories)):
            reject(400, 'INVALID_ELIGIBILITY', 'Choose one or more valid ride categories')
        chosen = set(categories)
        chosen.add('ECONOMY')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM fleet_drivers WHERE id=?', (driver_id,)).fetchone():
                reject(404, 'DRIVER_NOT_FOUND', 'Unknown driver')
            db.execute('DELETE FROM fleet_driver_eligibility WHERE driver_id=?', (driver_id,))
            for category in sorted(chosen):
                db.execute('INSERT INTO fleet_driver_eligibility VALUES (?,?,?,?)',
                           (driver_id, category, 'ADMIN', self.service.clock()))
            db.execute('DELETE FROM fleet_offers WHERE driver_id=?', (driver_id,))
            db.execute('DELETE FROM fleet_radar_candidates WHERE driver_id=?', (driver_id,))
            self._audit(db, driver_id, 'development-admin', 'ELIGIBILITY_' + '_'.join(sorted(chosen)))
        return self.status(driver_id)

    @staticmethod
    def label(place):
        name = str(place.get('name') or '').strip()
        address = str(place.get('address') or '').strip()
        return address if name.lower() in ('current location', 'my location', 'pickup') and address else (name or address)

    def _radar_cleanup(self, db):
        now = self.service.clock()
        rows = db.execute('SELECT ride_id,expires_ms,status FROM fleet_radar').fetchall()
        for ride_id, expires, status in rows:
            record = db.execute('SELECT payload FROM rides WHERE id=?', (ride_id,)).fetchone()
            searching = bool(record and json.loads(record[0]).get('status') == 'SEARCHING')
            if not searching:
                db.execute('UPDATE fleet_radar SET status="CLOSED" WHERE ride_id=?', (ride_id,))
                db.execute('DELETE FROM fleet_radar_candidates WHERE ride_id=?', (ride_id,))
            elif status == 'OPEN' and expires <= now:
                db.execute('UPDATE fleet_radar SET status="FALLBACK" WHERE ride_id=?', (ride_id,))
                db.execute('DELETE FROM fleet_radar_candidates WHERE ride_id=?', (ride_id,))

        # Explicit declines last for the lifetime of the unchanged searching ride. Remove their
        # rows only after the ride is gone or leaves SEARCHING, avoiding unbounded stale records.
        for driver_id, ride_id in db.execute('SELECT driver_id,ride_id FROM fleet_declines').fetchall():
            record = db.execute('SELECT payload FROM rides WHERE id=?', (ride_id,)).fetchone()
            if not record or json.loads(record[0]).get('status') != 'SEARCHING':
                db.execute('DELETE FROM fleet_declines WHERE driver_id=? AND ride_id=?',
                           (driver_id, ride_id))

    def _offer_json(self, db, ride, driver, expires, mode, candidate_count=1):
        draft, option = ride['draft'], ride['option']
        pickup, destination = draft['pickup'], draft['destination']
        distance = self.service.distance_km(driver[7], driver[8], pickup['latitude'], pickup['longitude'])
        owner = db.execute('SELECT first_name FROM passengers WHERE id=(SELECT owner FROM rides WHERE id=?)',
                           (ride['id'],)).fetchone()
        return {
            'id': ride['id'], 'rideId': ride['id'],
            'riderName': owner[0] if owner and owner[0] else 'Passenger',
            'pickup': pickup, 'destination': destination,
            'pickupName': self.label(pickup), 'destinationName': self.label(destination),
            'expiresAtEpochMs': expires, 'pickupDistanceKm': round(distance, 2),
            'pickupEtaMin': self.eta(distance),
            'tripDistanceKm': draft['routeEstimate']['distanceKm'],
            'tripEtaMin': draft['routeEstimate']['durationMinutes'],
            'fareCad': option['fareCad'],
            'driverEstimatedEarningsCad': option['breakdown']['driverGrossBeforeCostsCents'] / 100,
            'category': option['title'], 'offerMode': mode,
            'nearbyDriverCount': candidate_count,
        }

    def offer(self, driver_id):
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.cleanup(db)
            self._radar_cleanup(db)
            driver = db.execute('SELECT * FROM fleet_drivers WHERE id=?', (driver_id,)).fetchone()
            if not driver or not self.eligible(db, driver):
                return {}
            radar = db.execute('''SELECT r.ride_id,r.expires_ms FROM fleet_radar r
                JOIN fleet_radar_candidates c ON c.ride_id=r.ride_id
                WHERE c.driver_id=? AND r.status='OPEN' AND r.expires_ms>? ORDER BY r.created_ms LIMIT 1''',
                (driver_id, self.service.clock())).fetchone()
            if radar:
                record = db.execute('SELECT payload FROM rides WHERE id=?', (radar[0],)).fetchone()
                if record:
                    ride = json.loads(record[0])
                    count = db.execute('SELECT COUNT(*) FROM fleet_radar_candidates WHERE ride_id=?',
                                       (radar[0],)).fetchone()[0]
                    return self._offer_json(db, ride, driver, radar[1], 'RADAR', count)

            lease = db.execute('SELECT ride_id,expires_ms FROM fleet_offers WHERE driver_id=?',
                               (driver_id,)).fetchone()
            if lease:
                record = db.execute('SELECT payload FROM rides WHERE id=?', (lease[0],)).fetchone()
                if record:
                    return self._offer_json(db, json.loads(record[0]), driver, lease[1], 'EXCLUSIVE')

            reserved = {row[0] for row in db.execute('SELECT driver_id FROM fleet_offers')}
            reserved.update(row[0] for row in db.execute('''SELECT c.driver_id FROM fleet_radar_candidates c
                JOIN fleet_radar r ON r.ride_id=c.ride_id WHERE r.status='OPEN' AND r.expires_ms>?''',
                (self.service.clock(),)))
            claimed = {row[0] for row in db.execute('SELECT ride_id FROM fleet_offers')}
            claimed.update(row[0] for row in db.execute('SELECT ride_id FROM driver_offer_state WHERE expires_ms>?',
                                                        (self.service.clock(),)))
            radar_states = {row[0]: row[1] for row in db.execute('SELECT ride_id,status FROM fleet_radar')}
            drivers = [row for row in db.execute('SELECT * FROM fleet_drivers ORDER BY created_ms,id')
                       if self.eligible(db, row)]
            for ride in sorted(self.rides(db), key=lambda item: (item['requestedAtEpochMs'], item['id'])):
                if ride['status'] != 'SEARCHING' or ride['id'] in claimed:
                    continue
                pickup, tier = ride['draft']['pickup'], ride['option']['tier']
                choices = []
                for candidate in drivers:
                    if candidate[0] in reserved or not self.category_eligible(db, candidate[0], tier):
                        continue
                    if db.execute('SELECT 1 FROM fleet_declines WHERE driver_id=? AND ride_id=? AND until_ms>?',
                                  (candidate[0], ride['id'], self.service.clock())).fetchone():
                        continue
                    distance = self.service.distance_km(candidate[7], candidate[8],
                                                        pickup['latitude'], pickup['longitude'])
                    choices.append((distance, candidate[0]))
                # Radar is an account feature. Token-only compatibility drivers keep
                # the previous deterministic exclusive queue used by older builds.
                nearby = sorted(item for item in choices if item[0] <= RADAR_RADIUS_KM and
                                db.execute('SELECT 1 FROM fleet_logins WHERE driver_id=?', (item[1],)).fetchone())
                if len(nearby) >= 2 and ride['id'] not in radar_states:
                    expires = self.service.clock() + RADAR_WINDOW_MS
                    db.execute('INSERT INTO fleet_radar VALUES (?,? ,"OPEN",?)',
                               (ride['id'], expires, self.service.clock()))
                    for distance, candidate_id in nearby:
                        db.execute('INSERT INTO fleet_radar_candidates VALUES (?,?,?)',
                                   (ride['id'], candidate_id, distance))
                        reserved.add(candidate_id)
                    if any(candidate_id == driver_id for _, candidate_id in nearby):
                        return self._offer_json(db, ride, driver, expires, 'RADAR', len(nearby))
                elif choices and radar_states.get(ride['id']) != 'OPEN':
                    _, chosen = min(choices)
                    expires = self.service.clock() + EXCLUSIVE_WINDOW_MS
                    db.execute('INSERT INTO fleet_offers VALUES (?,?,?)', (chosen, ride['id'], expires))
                    reserved.add(chosen); claimed.add(ride['id'])
                    if chosen == driver_id:
                        return self._offer_json(db, ride, driver, expires, 'EXCLUSIVE')
            return {}

    def _radar_action(self, driver_id, ride_id, action):
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._radar_cleanup(db)
            candidate = db.execute('''SELECT r.expires_ms FROM fleet_radar r
                JOIN fleet_radar_candidates c ON c.ride_id=r.ride_id
                WHERE r.ride_id=? AND c.driver_id=? AND r.status='OPEN' AND r.expires_ms>?''',
                (ride_id, driver_id, self.service.clock())).fetchone()
            if not candidate:
                return False
            if action == 'decline':
                db.execute('DELETE FROM fleet_radar_candidates WHERE ride_id=? AND driver_id=?',
                           (ride_id, driver_id))
                db.execute('INSERT OR REPLACE INTO fleet_declines VALUES (?,?,?)',
                           (driver_id, ride_id, EXPLICIT_DECLINE_UNTIL_MS))
                remaining = db.execute('SELECT COUNT(*) FROM fleet_radar_candidates WHERE ride_id=?',
                                       (ride_id,)).fetchone()[0]
                if not remaining:
                    db.execute('UPDATE fleet_radar SET status="FALLBACK",expires_ms=? WHERE ride_id=?',
                               (self.service.clock(), ride_id))
                self._audit(db, driver_id, 'driver', 'RADAR_DECLINED_' + ride_id)
                return True
            record = db.execute('SELECT payload FROM rides WHERE id=?', (ride_id,)).fetchone()
            driver = db.execute('SELECT * FROM fleet_drivers WHERE id=?', (driver_id,)).fetchone()
            if not record or json.loads(record[0]).get('status') != 'SEARCHING' or not driver or not self.eligible(db, driver):
                reject(409, 'RADAR_MISSED', 'Another driver matched this ride')
            db.execute('UPDATE fleet_radar SET status="CLAIMED" WHERE ride_id=? AND status="OPEN"', (ride_id,))
            db.execute('DELETE FROM fleet_radar_candidates WHERE ride_id=?', (ride_id,))
            db.execute('INSERT OR REPLACE INTO fleet_offers VALUES (?,?,?)',
                       (driver_id, ride_id, self.service.clock() + 5_000))
            self._audit(db, driver_id, 'driver', 'RADAR_CLAIMED_' + ride_id)
            return True

    def action(self, driver_id, ride_id, action, body):
        if action in ('accept', 'decline'):
            radar = self._radar_action(driver_id, ride_id, action)
            if radar and action == 'decline':
                return {'status': 'DECLINED', 'offerMode': 'RADAR'}
        result = super().action(driver_id, ride_id, action, body)
        if action in ('decline', 'cancel'):
            with self.service.connect() as db:
                db.execute('UPDATE fleet_declines SET until_ms=? WHERE driver_id=? AND ride_id=?',
                           (EXPLICIT_DECLINE_UNTIL_MS, driver_id, ride_id))
        return result

    def passenger_availability(self, pickup, tier):
        with self.service.connect() as db:
            choices = [(self.service.distance_km(row[7], row[8], pickup['latitude'], pickup['longitude']), row[9])
                       for row in db.execute('SELECT * FROM fleet_drivers')
                       if self.eligible(db, row) and self.category_eligible(db, row[0], tier)]
        if not choices:
            return None
        distance, at = min(choices)
        return {'available': True, 'etaMinutes': self.eta(distance), 'distanceKm': round(distance, 2),
                'locationAgeSeconds': max(0, (self.service.clock() - at) // 1000),
                'availableDriverCount': len(choices),
                'dispatchMode': 'RADAR_ELIGIBLE' if sum(d <= RADAR_RADIUS_KM for d, _ in choices) >= 2 else 'EXCLUSIVE'}

    def history(self, driver_id):
        result = super().history(driver_id)
        with self.service.connect() as db:
            payloads = {json.loads(row[0])['id']: json.loads(row[0])
                        for row in db.execute('SELECT payload FROM rides')}
        for trip in result['trips']:
            ride = payloads.get(trip['id'], {})
            draft = ride.get('draft', {})
            pickup, destination = draft.get('pickup', {}), draft.get('destination', {})
            trip.update(
                pickup=self.label(pickup), destination=self.label(destination),
                pickupPoint={'latitude': pickup.get('latitude'), 'longitude': pickup.get('longitude')},
                destinationPoint={'latitude': destination.get('latitude'), 'longitude': destination.get('longitude')},
                routePoints=draft.get('routeEstimate', {}).get('path', []) or
                    [p for p in (pickup, destination) if p.get('latitude') is not None],
                category=ride.get('option', {}).get('title', ''),
            )
        return result
