"""Explicit one-time Owner bootstrap or invited staging Driver account creation."""
import argparse
import getpass
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import request_lock
from migrate import check
from server import Service
from staff38 import Staff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['owner', 'driver'])
    args = parser.parse_args()
    database = os.environ['DATABASE_URL']
    check(database)
    name = input('Username: ').strip().lower()
    password = getpass.getpass('Password (not displayed): ')
    if args.kind == 'owner':
        staff = Staff(database)
        with request_lock(database), staff.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM admin_staff LIMIT 1').fetchone():
                raise SystemExit('Staff already exist. Sign in as Owner to create additional staff.')
            staff._create(db, name, password, 'OWNER', 'explicit-bootstrap')
        print('Owner created. No shared admin token is enabled.')
    else:
        from settings import Settings
        settings = Settings.load()
        phone = input('Invited phone (+1...): ').strip()
        if phone not in settings.driver_phones:
            raise SystemExit('Phone is not on the staging invitation list')
        body = {'username': name, 'password': password, 'phone': phone,
                'name': input('Driver name: '), 'vehicle': input('Vehicle: '), 'plate': input('Plate: ')}
        service = Service(database)
        with request_lock(database):
            account = service.fleet.register_account(body)
            # Never print or retain the generated bearer credential. Driver logs in.
            service.fleet.logout(account['driverId'])
        print('Driver created as PENDING; document review and approval still required.')


if __name__ == '__main__': main()
