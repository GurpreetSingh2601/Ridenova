"""Shared operational controls used by web workers and scheduler."""
import hashlib
import hmac
import os
import time


def allow_request(database, secret, subject, limit, seconds=60):
    return allow_requests(database, secret, [(subject, limit, seconds)])


def allow_requests(database, secret, rules):
    """Apply all limits in one transaction/connection, including rejected attempts."""
    import psycopg
    now = int(time.time())
    with psycopg.connect(database, connect_timeout=5) as db:
        allowed = True
        for subject, limit, seconds in rules:
            key = hmac.new(secret.encode(), subject.encode(), hashlib.sha256).hexdigest()
            window = now // seconds
            count = db.execute('''INSERT INTO rate_limits(key,window_id,attempts,expires_ms) VALUES (%s,%s,1,%s)
                ON CONFLICT(key) DO UPDATE SET window_id=EXCLUDED.window_id,
                expires_ms=EXCLUDED.expires_ms,
                attempts=CASE WHEN rate_limits.window_id=EXCLUDED.window_id THEN rate_limits.attempts+1 ELSE 1 END
                RETURNING attempts''', (key, window, (window+1)*seconds*1000)).fetchone()[0]
            allowed = allowed and count <= limit
    return allowed


def heartbeat(database):
    import psycopg
    with psycopg.connect(database, connect_timeout=5) as db:
        db.execute('DELETE FROM rate_limits WHERE expires_ms < %s', (int(time.time()*1000),))
        db.execute('''INSERT INTO operational_heartbeats(name,at_ms,revision) VALUES ('scheduler',%s,%s)
            ON CONFLICT(name) DO UPDATE SET at_ms=EXCLUDED.at_ms,revision=EXCLUDED.revision''',
                   (int(time.time()*1000), os.environ.get('RENDER_GIT_COMMIT', 'local')))


def ready(database):
    import psycopg
    from migrate import check
    check(database)
    with psycopg.connect(database, connect_timeout=5) as db:
        owner = db.execute("SELECT 1 FROM admin_staff WHERE role='OWNER' AND active=1 LIMIT 1").fetchone()
        tick = db.execute("SELECT at_ms,revision FROM operational_heartbeats WHERE name='scheduler'").fetchone()
    return bool(owner and tick and 0 <= int(time.time()*1000)-tick[0] < 45000
                and tick[1] == os.environ.get('RENDER_GIT_COMMIT', 'local'))
