"""Build 34 post-trip feedback and support-case domain.

The development backend keeps these records separate from ride payloads so feedback can
be updated without mutating the immutable fare and trip snapshots.
"""
import json
import re
import secrets


class ExperienceError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def reject(status, code, message):
    raise ExperienceError(status, code, message)


RATING_TAGS = {
    'SAFE_DRIVING', 'FRIENDLY', 'CLEAN_VEHICLE', 'GREAT_ROUTE', 'ON_TIME',
    'RESPECTFUL', 'CLEAR_COMMUNICATION', 'EASY_PICKUP', 'OTHER'
}
CASE_CATEGORIES = {'SAFETY', 'FARE', 'LOST_ITEM', 'DRIVER', 'PASSENGER', 'APP', 'OTHER'}
CASE_STATUSES = {'OPEN', 'IN_REVIEW', 'RESOLVED'}


class Experience:
    def __init__(self, service):
        self.service = service
        if service.postgres:
            return
        with service.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS ride_feedback (
                    ride_id TEXT NOT NULL,
                    author_role TEXT NOT NULL CHECK(author_role IN ('PASSENGER','DRIVER')),
                    author_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
                    tags_json TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    created_ms INTEGER NOT NULL,
                    updated_ms INTEGER NOT NULL,
                    PRIMARY KEY(ride_id, author_role));
                CREATE INDEX IF NOT EXISTS feedback_target ON ride_feedback(target_id, author_role);
                CREATE TABLE IF NOT EXISTS support_cases (
                    id TEXT PRIMARY KEY,
                    ride_id TEXT,
                    reporter_role TEXT NOT NULL CHECK(reporter_role IN ('PASSENGER','DRIVER')),
                    reporter_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    admin_note TEXT NOT NULL,
                    created_ms INTEGER NOT NULL,
                    updated_ms INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS cases_reporter ON support_cases(reporter_role, reporter_id, created_ms DESC);
                CREATE INDEX IF NOT EXISTS cases_status ON support_cases(status, updated_ms DESC);
            ''')

    @staticmethod
    def _ride_id(value):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
            reject(404, 'RIDE_NOT_FOUND', 'Ride not found')
        return value

    def _ride(self, db, ride_id):
        row = db.execute('SELECT owner,payload FROM rides WHERE id=?', (self._ride_id(ride_id),)).fetchone()
        if not row:
            reject(404, 'RIDE_NOT_FOUND', 'Ride not found')
        return row[0], json.loads(row[1])

    def _authorize_ride(self, db, role, actor_id, ride_id):
        owner, ride = self._ride(db, ride_id)
        authorized = owner == actor_id if role == 'PASSENGER' else ride.get('fleetDriverId') == actor_id
        if not authorized:
            reject(404, 'RIDE_NOT_FOUND', 'Ride not found')
        return owner, ride

    @staticmethod
    def _feedback_json(row):
        if not row:
            return None
        return {'rideId': row[0], 'authorRole': row[1], 'stars': row[2],
                'tags': json.loads(row[3]), 'comment': row[4],
                'createdAtEpochMs': row[5], 'updatedAtEpochMs': row[6]}

    def ride_experience(self, role, actor_id, ride_id):
        with self.service.connect() as db:
            _, ride = self._authorize_ride(db, role, actor_id, ride_id)
            own = db.execute('SELECT ride_id,author_role,stars,tags_json,comment,created_ms,updated_ms '
                             'FROM ride_feedback WHERE ride_id=? AND author_role=?',
                             (ride_id, role)).fetchone()
            case_count = db.execute('SELECT COUNT(*) FROM support_cases WHERE ride_id=? AND reporter_role=? AND reporter_id=?',
                                    (ride_id, role, actor_id)).fetchone()[0]
        return {'rideId': ride_id, 'rideStatus': ride.get('status'),
                'canRate': ride.get('status') == 'COMPLETED',
                'rating': self._feedback_json(own), 'supportCaseCount': case_count}

    def rate(self, role, actor_id, ride_id, body):
        stars = body.get('stars')
        if isinstance(stars, bool) or not isinstance(stars, int) or stars not in range(1, 6):
            reject(400, 'INVALID_RATING', 'Choose a rating from 1 to 5 stars')
        tags = body.get('tags', [])
        if not isinstance(tags, list) or len(tags) > 5 or any(tag not in RATING_TAGS for tag in tags) or len(set(tags)) != len(tags):
            reject(400, 'INVALID_RATING_TAGS', 'Choose up to five valid feedback tags')
        comment = body.get('comment', '')
        if not isinstance(comment, str) or len(comment.strip()) > 500:
            reject(400, 'INVALID_COMMENT', 'Feedback must be 500 characters or fewer')
        now = self.service.clock()
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            owner, ride = self._authorize_ride(db, role, actor_id, ride_id)
            if ride.get('status') != 'COMPLETED':
                reject(409, 'RIDE_NOT_COMPLETED', 'Feedback is available after the ride is completed')
            target = ride.get('fleetDriverId') if role == 'PASSENGER' else owner
            if not target:
                reject(409, 'RATING_TARGET_MISSING', 'This ride does not have a rating recipient')
            existing = db.execute('SELECT created_ms FROM ride_feedback WHERE ride_id=? AND author_role=?',
                                  (ride_id, role)).fetchone()
            created = existing[0] if existing else now
            db.execute('''INSERT INTO ride_feedback
                (ride_id,author_role,author_id,target_id,stars,tags_json,comment,created_ms,updated_ms)
                VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(ride_id,author_role) DO UPDATE SET
                stars=excluded.stars,tags_json=excluded.tags_json,comment=excluded.comment,updated_ms=excluded.updated_ms''',
                (ride_id, role, actor_id, target, stars, json.dumps(tags), comment.strip(), created, now))
        return self.ride_experience(role, actor_id, ride_id)

    @staticmethod
    def _case_json(row, include_private=False):
        value = {'id': row[0], 'rideId': row[1], 'reporterRole': row[2],
                 'category': row[3], 'description': row[4], 'status': row[5],
                 'createdAtEpochMs': row[7], 'updatedAtEpochMs': row[8]}
        if include_private:
            value['reporterId'] = row[9]
        if row[6]:
            value['adminNote'] = row[6]
        return value

    def create_case(self, role, actor_id, body):
        category = body.get('category')
        description = body.get('description')
        ride_id = body.get('rideId') or None
        if category not in CASE_CATEGORIES:
            reject(400, 'INVALID_CASE_CATEGORY', 'Choose a valid support category')
        if not isinstance(description, str) or not 10 <= len(description.strip()) <= 1000:
            reject(400, 'INVALID_CASE_DESCRIPTION', 'Describe the issue in 10 to 1000 characters')
        now, case_id = self.service.clock(), 'case_' + secrets.token_hex(10)
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if ride_id:
                self._authorize_ride(db, role, actor_id, ride_id)
            db.execute('INSERT INTO support_cases VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (case_id, ride_id, role, actor_id, category, description.strip(),
                        'OPEN', '', now, now))
        return self.get_case(role, actor_id, case_id)

    def get_case(self, role, actor_id, case_id):
        with self.service.connect() as db:
            row = db.execute('SELECT id,ride_id,reporter_role,category,description,status,admin_note,created_ms,updated_ms,reporter_id '
                             'FROM support_cases WHERE id=? AND reporter_role=? AND reporter_id=?',
                             (case_id, role, actor_id)).fetchone()
        if not row:
            reject(404, 'CASE_NOT_FOUND', 'Support case not found')
        return self._case_json(row)

    def list_cases(self, role, actor_id):
        with self.service.connect() as db:
            rows = db.execute('SELECT id,ride_id,reporter_role,category,description,status,admin_note,created_ms,updated_ms,reporter_id '
                              'FROM support_cases WHERE reporter_role=? AND reporter_id=? ORDER BY created_ms DESC LIMIT 100',
                              (role, actor_id)).fetchall()
        return {'cases': [self._case_json(row) for row in rows]}

    def admin_cases(self):
        with self.service.connect() as db:
            rows = db.execute('SELECT id,ride_id,reporter_role,category,description,status,admin_note,created_ms,updated_ms,reporter_id '
                              'FROM support_cases ORDER BY updated_ms DESC LIMIT 250').fetchall()
        return {'cases': [self._case_json(row, True) for row in rows]}

    def update_case(self, case_id, body):
        status, note = body.get('status'), body.get('adminNote', '')
        if status not in CASE_STATUSES:
            reject(400, 'INVALID_CASE_STATUS', 'Choose OPEN, IN_REVIEW or RESOLVED')
        if not isinstance(note, str) or len(note.strip()) > 1000:
            reject(400, 'INVALID_ADMIN_NOTE', 'Admin note must be 1000 characters or fewer')
        with self.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute('UPDATE support_cases SET status=?,admin_note=?,updated_ms=? WHERE id=?',
                                 (status, note.strip(), self.service.clock(), case_id)).rowcount
            if not changed:
                reject(404, 'CASE_NOT_FOUND', 'Support case not found')
            row = db.execute('SELECT id,ride_id,reporter_role,category,description,status,admin_note,created_ms,updated_ms,reporter_id '
                             'FROM support_cases WHERE id=?', (case_id,)).fetchone()
        return self._case_json(row, True)

    def admin_feedback(self):
        with self.service.connect() as db:
            rows = db.execute('SELECT ride_id,author_role,stars,tags_json,comment,created_ms,updated_ms '
                              'FROM ride_feedback ORDER BY updated_ms DESC LIMIT 250').fetchall()
        return {'feedback': [self._feedback_json(row) for row in rows]}

    def dashboard(self):
        with self.service.connect() as db:
            rating = db.execute('SELECT COUNT(*),COALESCE(AVG(stars),0) FROM ride_feedback').fetchone()
            cases = {row[0]: row[1] for row in db.execute('SELECT status,COUNT(*) FROM support_cases GROUP BY status')}
        return {'ratingCount': rating[0], 'averageRating': round(float(rating[1]), 2),
                'openCases': cases.get('OPEN', 0), 'inReviewCases': cases.get('IN_REVIEW', 0),
                'resolvedCases': cases.get('RESOLVED', 0)}
