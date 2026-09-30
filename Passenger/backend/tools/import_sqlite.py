"""Copy an accepted Build 40 SQLite snapshot into an EMPTY migrated PostgreSQL DB.
Never modifies the source. Stop the old API before taking the final cutover copy.
"""
import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import request_lock
from migrate import check


def row_digest(rows):
    def cell(value):
        if isinstance(value, (bytes, memoryview)):
            return {'bytes': bytes(value).hex()}
        return value
    encoded = sorted(json.dumps([cell(v) for v in row], ensure_ascii=False, separators=(',', ':')) for row in rows)
    return hashlib.sha256('\n'.join(encoded).encode()).hexdigest()


def import_database(source, target, report_path):
    import psycopg
    from psycopg import sql
    source = Path(source).resolve(strict=True)
    check(target)
    with tempfile.TemporaryDirectory() as temporary:
        snapshot = Path(temporary) / 'snapshot.sqlite3'
        original = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
        copy = sqlite3.connect(snapshot)
        try:
            original.backup(copy)
            if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or copy.execute('PRAGMA foreign_key_check').fetchall():
                raise RuntimeError('SQLite integrity/foreign-key check failed')
            tables = [r[0] for r in copy.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
            report = {'sourceSha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(), 'tables': {}}
            with request_lock(target), psycopg.connect(target) as db:
                target_tables = {r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
                operational = {'schema_migrations', 'rate_limits', 'operational_heartbeats', 'import_receipts'}
                baseline = Path(__file__).resolve().parents[1] / 'migrations/001_build40_baseline.sql'
                finance = Path(__file__).resolve().parents[1] / 'migrations/003_build42_finance_boost.sql'
                import re
                baseline_tables = re.findall(r'CREATE TABLE (\w+)', baseline.read_text())
                finance_tables = re.findall(r'CREATE TABLE (\w+)', finance.read_text())
                if not set(baseline_tables) <= set(tables) or set(tables) - set(baseline_tables) - set(finance_tables):
                    raise RuntimeError('Source must contain complete accepted baseline and only known Build 42 extensions')
                if set(baseline_tables + finance_tables) != target_tables - operational:
                    raise RuntimeError('Target table inventory differs from expected migrations')
                for table in target_tables - {'schema_migrations'}:
                    if db.execute(sql.SQL('SELECT 1 FROM {} LIMIT 1').format(sql.Identifier(table))).fetchone():
                        raise RuntimeError('Target is not empty; refusing to overwrite data')
                # Versioned baseline lists parent tables before their children.
                ordered = baseline_tables + [table for table in finance_tables if table in tables]
                for table in ordered:
                    info = copy.execute('PRAGMA table_info("' + table + '")').fetchall()
                    columns = [r[1] for r in info]
                    pg_columns = [r[0] for r in db.execute('SELECT column_name FROM information_schema.columns '
                        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,))]
                    if columns != pg_columns:
                        raise RuntimeError('Column mismatch in ' + table)
                    rows = copy.execute('SELECT * FROM "' + table + '"').fetchall()
                    if rows:
                        query = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),
                            sql.SQL(',').join(map(sql.Identifier, columns)), sql.SQL(',').join(sql.Placeholder() for _ in columns))
                        with db.cursor() as cursor:
                            cursor.executemany(query, rows)
                    restored = db.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(table))).fetchall()
                    if row_digest(rows) != row_digest(restored):
                        raise RuntimeError('Content verification failed for ' + table)
                    report['tables'][table] = {'rows': len(rows), 'sha256': row_digest(rows)}
                for table, column in (('events', 'sequence'), ('fleet_audit', 'id'), ('admin_audit', 'id')):
                    db.execute(sql.SQL("SELECT setval(pg_get_serial_sequence(%s,%s),COALESCE(MAX({}),1),COUNT(*)>0) FROM {}").format(
                        sql.Identifier(column), sql.Identifier(table)), (table, column))
                # Environment boundary: retain accounts, password hashes, ride/event/
                # ledger history, but never reuse development bearer credentials.
                now = int(time.time()*1000)
                db.execute('UPDATE auth_sessions SET revoked_ms=%s WHERE revoked_ms IS NULL', (now,))
                db.execute('DELETE FROM admin_sessions')
                for (driver_id,) in db.execute('SELECT driver_id FROM fleet_credentials').fetchall():
                    db.execute('UPDATE fleet_credentials SET token_hash=%s WHERE driver_id=%s',
                               (hashlib.sha256(secrets.token_bytes(48)).hexdigest(), driver_id))
                db.execute('UPDATE otp_challenges SET consumed_ms=%s WHERE consumed_ms IS NULL', (now,))
                db.execute('UPDATE fleet_drivers SET online=0,located_ms=NULL')
                db.execute('UPDATE driver_state SET online=0')
                for table in ('fleet_offers', 'fleet_radar_candidates', 'fleet_radar', 'driver_offer_state', 'driver_presence'):
                    db.execute(sql.SQL('DELETE FROM {}').format(sql.Identifier(table)))
                report['environmentReset'] = 'Sessions/OTP revoked; driver tokens rotated to unknown values and transient offers cleared; drivers offline. Accounts, passwords, rides, declines, documents, history and earnings preserved.'
                db.execute('INSERT INTO import_receipts(source_sha256,report) VALUES (%s,%s)',
                           (report['sourceSha256'], json.dumps(report)))
            # Write report only after successful commit. DB also retains a receipt.
            Path(report_path).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
            return report
        finally:
            original.close()
            copy.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--report', default='import-report.json')
    parser.add_argument('--confirm-offline', action='store_true', required=True)
    args = parser.parse_args()
    result = import_database(args.source, os.environ['DATABASE_URL'], args.report)
    print('Import committed and verified:', len(result['tables']), 'tables. Source unchanged.')
