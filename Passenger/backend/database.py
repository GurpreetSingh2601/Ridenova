"""Explicit PostgreSQL compatibility boundary for the existing domain SQL.

SQLite remains the development/regression database. PostgreSQL schema changes
are exclusively applied by migrate.py, never by a web worker.
"""
import re
import sqlite3
from contextlib import contextmanager

WRITE_LOCK = 410001
REQUEST_LOCK = 410002


def is_postgres(database):
    return str(database).startswith(('postgresql://', 'postgres://'))


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


# These are the only legacy REPLACE statements. Updating preserves references;
# unlike SQLite REPLACE, this never deletes/reinserts a referenced parent row.
UPSERTS = {
    'fleet_declines': (('driver_id', 'ride_id', 'until_ms'), ('driver_id', 'ride_id')),
    'fleet_offers': (('driver_id', 'ride_id', 'expires_ms'), ('driver_id',)),
    'fleet_pin_attempts': (('ride_id', 'attempts', 'until_ms'), ('ride_id',)),
    'fleet_login_attempts': (('username', 'failures', 'until_ms'), ('username',)),
    'fleet_logins': (('driver_id', 'username', 'salt', 'password_hash', 'must_reset', 'phone'), ('driver_id',)),
    'fleet_driver_eligibility': (('driver_id', 'category', 'source', 'updated_ms'), ('driver_id', 'category')),
}


def translate(sql):
    """Translate the small, audited SQLite dialect; never interpolate data."""
    sql = sql.strip().rstrip(';')
    if sql.upper() == 'BEGIN IMMEDIATE':
        return f'SELECT pg_advisory_xact_lock({WRITE_LOCK})'
    if re.match(r'^(PRAGMA|CREATE|ALTER|DROP)\b', sql, re.I):
        raise ValueError('Runtime DDL is disabled; run migrate.py first')
    # Legacy SQL uses double quotes for string constants, never identifiers.
    sql = re.sub(r'"([^"\n]*)"', lambda m: "'" + m[1].replace("'", "''") + "'", sql)
    sql = re.sub(r"json_extract\((\w+),'\$\.(\w+)'\)", r"(\1::jsonb->>'\2')", sql)
    sql = sql.replace(' AS INTEGER)', ' AS BIGINT)').replace('instr(id,?)', 'strpos(id,?)')
    sql = sql.replace(' LIKE ', ' ILIKE ')  # Preserve SQLite's case-insensitive admin searches.
    ignore = bool(re.match(r'INSERT OR IGNORE ', sql, re.I))
    replace = re.match(r'INSERT OR REPLACE INTO (\w+)\s*(\([^)]*\))?', sql, re.I)
    if replace:
        columns, keys = UPSERTS[replace[1]]
        if replace[2]:
            columns = tuple(c.strip() for c in replace[2][1:-1].split(','))
        elif replace[1] == 'fleet_logins':
            columns = columns[:5]  # pre-phone superclass path supplies five values
            sql = sql.replace('fleet_logins', 'fleet_logins (' + ','.join(columns) + ')', 1)
        sql = re.sub('INSERT OR REPLACE', 'INSERT', sql, count=1, flags=re.I)
        sql += ' ON CONFLICT (' + ','.join(keys) + ') DO UPDATE SET ' + ','.join(
            f'{c}=EXCLUDED.{c}' for c in columns if c not in keys)
    if ignore:
        sql = re.sub('INSERT OR IGNORE', 'INSERT', sql, count=1, flags=re.I) + ' ON CONFLICT DO NOTHING'
    # qmarks inside literal strings are not placeholders.
    parts = re.split(r"('(?:''|[^'])*')", sql)
    return ''.join(p if i % 2 else p.replace('?', '%s') for i, p in enumerate(parts))


class PostgresConnection:
    def __init__(self, database):
        import psycopg
        self.raw = psycopg.connect(database, connect_timeout=10,
            options='-c statement_timeout=15000 -c lock_timeout=10000 -c idle_in_transaction_session_timeout=30000')

    def execute(self, sql, parameters=()):
        import psycopg
        try:
            translated = translate(sql)
            if parameters:
                translated = re.sub(r'%(?!s)', '%%', translated)
            return self.raw.execute(translated, parameters or None)
        except psycopg.IntegrityError as exc:
            # Domain error handling remains identical to SQLite. Caller exits
            # the context and rolls back; never continue an aborted transaction.
            raise sqlite3.IntegrityError('Database constraint rejected operation') from exc

    def executescript(self, _):
        raise RuntimeError('Run versioned migrations before starting PostgreSQL services')

    def commit(self): return self.raw.commit()
    def rollback(self): return self.raw.rollback()
    def close(self): return self.raw.close()
    def __enter__(self): return self
    def __exit__(self, *args): return self.raw.__exit__(*args)


def connect(database):
    if is_postgres(database):
        return PostgresConnection(database)
    db = sqlite3.connect(database, timeout=10, factory=ClosingConnection)
    db.execute('PRAGMA foreign_keys=ON')
    return db


@contextmanager
def request_lock(database):
    """Cross-worker gate for legacy multi-transaction workflows.

    All staging API requests and scheduler ticks take this session lock. This
    intentionally prioritizes correctness over throughput for controlled staging.
    Readiness/health bypass it. Do not claim this is a high-scale architecture.
    """
    if not is_postgres(database):
        yield
        return
    import psycopg
    with psycopg.connect(database, autocommit=True, connect_timeout=10,
                         options='-c statement_timeout=20000 -c lock_timeout=15000') as db:
        db.execute('SELECT pg_advisory_lock(%s)', (REQUEST_LOCK,))
        try:
            yield
        finally:
            db.execute('SELECT pg_advisory_unlock(%s)', (REQUEST_LOCK,))
