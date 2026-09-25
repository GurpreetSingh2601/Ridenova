"""Create and validate a migrated Build 41 copy of an existing RideNova SQLite database.

This script never modifies the source database and refuses to overwrite the destination.
Stop the old backend first, then point Build 41 at the validated destination copy.
"""
from argparse import ArgumentParser
from pathlib import Path
import sqlite3
import sys


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Existing RideNova SQLite database')
    parser.add_argument('--destination', required=True, help='New Build 41 database copy')
    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    destination = Path(args.destination).expanduser().resolve()
    if not source.is_file():
        parser.error(f'Source database does not exist: {source}')
    if destination.exists():
        parser.error(f'Destination already exists; it will not be overwritten: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as old, sqlite3.connect(destination) as new:
        old.backup(new)
    backend = Path(__file__).resolve().parent / 'Passenger' / 'backend'
    sys.path.insert(0, str(backend))
    from server import Service
    from staff38 import Staff
    Service(destination)  # Additive CREATE/ALTER migrations run against the copy only.
    Staff(destination)  # Create staff/session/audit tables without creating credentials.
    with sqlite3.connect(destination) as database:
        integrity = database.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise SystemExit(f'Migrated copy failed integrity_check: {integrity}')
        tables = {row[0] for row in database.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        required = {'rides', 'quotes', 'events', 'passengers', 'fleet_drivers',
                    'admin_staff', 'admin_sessions'}
        missing = sorted(required - tables)
        if missing:
            raise SystemExit(f'Migrated copy is missing tables: {missing}')
        rides = database.execute('SELECT COUNT(*) FROM rides').fetchone()[0]
        passengers = database.execute('SELECT COUNT(*) FROM passengers').fetchone()[0]
        drivers = database.execute('SELECT COUNT(*) FROM fleet_drivers').fetchone()[0]
    print(f'PASS: Build 41 database copy created and validated: {destination}')
    print(f'Preserved rows: {rides} rides, {passengers} passengers, {drivers} fleet drivers')
    print('The source database was not modified.')


if __name__ == '__main__':
    main()
