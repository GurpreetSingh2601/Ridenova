"""Local end-to-end demo client. Never uses a real payment or real driver."""
import argparse
import json
import os
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['login', 'book', 'list', 'cancel', 'advance', 'events'])
    parser.add_argument('--ride')
    parser.add_argument('--schedule-minutes', type=int, help='Book this many minutes ahead (15–43200); optional')
    parser.add_argument('--status', choices=['DRIVER_ASSIGNED', 'DRIVER_ARRIVED', 'TRIP_STARTED', 'COMPLETED'])
    args = parser.parse_args()
    access_token = os.environ.get('RIDENOVA_DEV_ACCESS_TOKEN')
    def call(path, body=None, admin=False, authenticated=True):
        headers = {'Content-Type': 'application/json', 'X-RideNova-Session': 'development-cli-session-0001'}
        if admin:
            token = os.environ.get('RIDENOVA_DEV_ADMIN_TOKEN')
            if not token:
                parser.error('Set RIDENOVA_DEV_ADMIN_TOKEN in both server and client terminals')
            headers['Authorization'] = 'Bearer ' + token
        elif authenticated:
            if not access_token:
                parser.error('Set RIDENOVA_DEV_ACCESS_TOKEN, or run the login action first')
            headers['Authorization'] = 'Bearer ' + access_token
        req = urllib.request.Request('http://127.0.0.1:8080' + path,
              data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)
    if args.action == 'login':
        phone = input('Canadian phone (+1): ').strip()
        challenge = call('/v1/auth/request-otp', {'phone': phone}, authenticated=False)
        code = input(f"Development code ({challenge.get('developmentCode', 'check SMS')}): ").strip()
        result = call('/v1/auth/verify-otp', {'challengeId': challenge['challengeId'], 'code': code}, authenticated=False)
        print('Set RIDENOVA_DEV_ACCESS_TOKEN to this short-lived development token:')
        print(result['accessToken'])
        return
    if args.action == 'book':
        booking = {
            'pickup': {'name': 'Vancouver', 'address': 'Downtown Vancouver', 'latitude': 49.28, 'longitude': -123.12},
            'destination': {'name': 'Burnaby', 'address': 'Burnaby', 'latitude': 49.25, 'longitude': -122.98},
            'scheduled': args.schedule_minutes is not None}
        if args.schedule_minutes is not None:
            booking.update(scheduledAtEpochMs=int(time.time() * 1000) + args.schedule_minutes * 60000,
                           scheduleTimeZone='UTC')
        quote = call('/v1/passenger/quotes', booking)
        print(json.dumps(quote, indent=2))
        if input('Create this DEVELOPMENT ride? Type yes: ').strip() != 'yes':
            return
        result = call('/v1/passenger/rides', {'quoteToken': quote['quoteToken'], 'rideOption': {'tier': 'ECONOMY'}})
    elif args.action == 'list':
        result = call('/v1/passenger/rides')
    else:
        if not args.ride:
            parser.error('--ride is required')
        if args.action == 'cancel':
            result = call('/v1/passenger/rides/' + args.ride + '/cancel', {})
        elif args.action == 'events':
            result = call('/v1/admin/rides/' + args.ride + '/events', admin=True)
        else:
            if not args.status:
                parser.error('--status is required')
            result = call('/v1/admin/rides/' + args.ride + '/transition', {'status': args.status}, admin=True)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
