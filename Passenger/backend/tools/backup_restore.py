"""Logical backup and restore drill. PostgreSQL client tools must match server major.
Set DATABASE_URL for backup, RESTORE_DATABASE_URL for a disposable empty target.
Backup files contain sensitive data: keep encrypted, access-controlled and off-repo.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import request_lock
from tools.import_sqlite import row_digest


def inventory(database):
    import psycopg
    from psycopg import sql
    with psycopg.connect(database) as db:
        db.execute("SET TIME ZONE 'UTC'")
        tables = [r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
        result = {}
        for table in tables:
            rows = db.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(table))).fetchall()
            # Timestamps in migration/import receipts are normalized for JSON.
            rows = [tuple(v.isoformat() if hasattr(v, 'isoformat') else v for v in row) for row in rows]
            result[table] = {'rows': len(rows), 'sha256': row_digest(rows)}
        return result


def run_tool(command, database):
    from psycopg.conninfo import conninfo_to_dict
    # libpq's PGDATABASE is a database *name*, not a URI. A complete URI in
    # PGDATABASE makes pg_dump attempt to connect to a database with that
    # literal name. Parse it with libpq-compatible psycopg instead, retaining
    # credentials only in the child environment (never argv or error output).
    fields = {
        'host': 'PGHOST', 'hostaddr': 'PGHOSTADDR', 'port': 'PGPORT',
        'dbname': 'PGDATABASE', 'user': 'PGUSER', 'password': 'PGPASSWORD',
        'passfile': 'PGPASSFILE', 'sslmode': 'PGSSLMODE',
        'sslrootcert': 'PGSSLROOTCERT', 'sslcert': 'PGSSLCERT',
        'sslkey': 'PGSSLKEY', 'sslcrl': 'PGSSLCRL',
        'sslcrldir': 'PGSSLCRLDIR', 'channel_binding': 'PGCHANNELBINDING',
        'gssencmode': 'PGGSSENCMODE', 'target_session_attrs': 'PGTARGETSESSIONATTRS',
    }
    connection = conninfo_to_dict(database)
    unsupported = set(connection) - set(fields)
    if unsupported:
        raise RuntimeError('Unsupported PostgreSQL connection option for backup tool')
    environment = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
    environment.update({fields[key]: str(value) for key, value in connection.items()})
    environment['PGCONNECT_TIMEOUT'] = '10'
    result = subprocess.run(command, env=environment, capture_output=True)
    if result.returncode:
        raise RuntimeError(command[0] + ' failed; check tool version, access and target. Credentials suppressed.')


def backup(database, path):
    path = Path(path)
    if path.exists() or path.with_suffix(path.suffix + '.json').exists():
        raise RuntimeError('Refusing to overwrite an existing backup')
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with request_lock(database):
            # Web requests and scheduler are paused by the same database gate.
            # Operational rate-limit counters are transient and may still change.
            run_tool(['pg_dump', '--format=custom', '--no-owner', '--no-privileges',
                      '--exclude-table-data=rate_limits', '--file', str(path)], database)
            contents = inventory(database)
            contents['rate_limits'] = {'rows': 0, 'sha256': row_digest([])}
        manifest = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'tables': contents}
        path.with_suffix(path.suffix + '.json').write_text(json.dumps(manifest, indent=2) + '\n')
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return manifest


def restore(database, path):
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    path = Path(path)
    manifest = json.loads(path.with_suffix(path.suffix + '.json').read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['sha256']:
        raise RuntimeError('Backup checksum mismatch')
    with psycopg.connect(database) as db:
        if db.execute("SELECT 1 FROM pg_tables WHERE schemaname='public' LIMIT 1").fetchone():
            raise RuntimeError('Restore target must be empty; refusing destructive restore')
    # pg_restore only executes SQL when --dbname is supplied. Pass the plain
    # database name in argv; host/user/password remain in the child env.
    name = conninfo_to_dict(database)['dbname']
    run_tool(['pg_restore', '--exit-on-error', '--single-transaction', '--no-owner', '--no-privileges',
              '--dbname', name, str(path)], database)
    if inventory(database) != manifest['tables']:
        raise RuntimeError('Restore contents do not match backup manifest')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'restore-check'])
    parser.add_argument('file')
    args = parser.parse_args()
    if args.action == 'backup':
        backup(os.environ['DATABASE_URL'], args.file)
    else:
        target = os.environ['RESTORE_DATABASE_URL']
        if target == os.environ.get('DATABASE_URL'):
            raise SystemExit('Restore target must differ from the source')
        restore(target, args.file)
    print(args.action, 'completed and verified')
