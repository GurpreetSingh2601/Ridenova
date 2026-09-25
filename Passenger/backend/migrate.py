"""Versioned PostgreSQL migrations. Set DATABASE_URL; never pass secrets in argv."""
import hashlib
import os
from pathlib import Path

MIGRATIONS = Path(__file__).with_name('migrations')


def apply(database):
    import psycopg
    with psycopg.connect(database, connect_timeout=10) as db:
        db.execute('SELECT pg_advisory_xact_lock(410000)')
        db.execute('CREATE TABLE IF NOT EXISTS schema_migrations '
                   '(version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())')
        existing = dict(db.execute('SELECT version,checksum FROM schema_migrations').fetchall())
        files = {p.name: p for p in sorted(MIGRATIONS.glob('*.sql'))}
        if set(existing) - set(files):
            raise RuntimeError('Database has newer migrations; use a compatible release')
        for name, path in files.items():
            sql = path.read_text(encoding='utf-8')
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            if name in existing:
                if existing[name] != checksum:
                    raise RuntimeError('Applied migration checksum mismatch: ' + name)
                continue
            db.execute(sql)
            db.execute('INSERT INTO schema_migrations(version,checksum) VALUES (%s,%s)', (name, checksum))
            print('Applied', name)


def check(database):
    import psycopg
    with psycopg.connect(database, connect_timeout=5) as db:
        actual = dict(db.execute('SELECT version,checksum FROM schema_migrations').fetchall())
    expected = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in MIGRATIONS.glob('*.sql')}
    if actual != expected:
        raise RuntimeError('Migration mismatch; run migrate.py with this release before starting')


if __name__ == '__main__':
    apply(os.environ['DATABASE_URL'])
