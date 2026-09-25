"""Unauthenticated deployment smoke test; no rides/data mutations."""
import argparse
import json
import urllib.request
import urllib.error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origin')
    args = parser.parse_args()
    if not args.origin.startswith('https://'): raise SystemExit('Use HTTPS')
    origin = args.origin.rstrip('/')
    for path in ('/health', '/ready', '/admin', '/v1/admin/overview'):
        try:
            response = urllib.request.urlopen(origin + path, timeout=20)
        except urllib.error.HTTPError as exc: response = exc
        with response:
            data = response.read()
            expected = 401 if path.endswith('/overview') else 200
            assert response.status == expected, f'{path}: expected {expected}, got {response.status}'
            if path == '/health':
                health = json.loads(data)
                assert health['build'] == 41 and health['environment'] == 'staging'
            if path == '/admin': assert b'STAGING - invited tests only' in data
            assert response.headers.get('Strict-Transport-Security'), 'Missing HTTPS security header'
        print('PASS', path)


if __name__ == '__main__': main()
