"""Exercise the real Gunicorn transport against a disposable local SQLite DB."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT/'Passenger/backend'
sys.path.insert(0, str(BACKEND))
from server import Service
from staff38 import Staff


def main():
    with tempfile.TemporaryDirectory() as temp:
        database = str(Path(temp)/'smoke.sqlite3')
        Service(database); Staff(database)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
        environment = dict(os.environ, RIDENOVA_ENVIRONMENT='development', RIDENOVA_DATABASE=database,
                           DATABASE_URL='', RIDENOVA_OWNER_USERNAME='', RIDENOVA_OWNER_PASSWORD='')
        command = [sys.executable, '-m', 'gunicorn', '--bind', f'127.0.0.1:{port}', '--workers', '2', 'wsgi:create_app()']
        origin = f'http://127.0.0.1:{port}'
        def call(path, body=None, token=None):
            headers = {'Content-Type': 'application/json'}
            if token: headers['Authorization'] = 'Bearer '+token
            request = urllib.request.Request(origin+path, data=None if body is None else json.dumps(body).encode(), headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.headers, response.read()
        def start():
            process = subprocess.Popen(command, env=environment, cwd=BACKEND, stdout=subprocess.DEVNULL)
            for _ in range(100):
                if process.poll() is not None: raise RuntimeError('Gunicorn exited during startup')
                try:
                    call('/health'); return process
                except OSError: time.sleep(.1)
            process.terminate(); process.wait(10); raise RuntimeError('Gunicorn startup timed out')
        process = start()
        try:
            assert json.loads(call('/health')[2])['build'] == 42
            status, headers, body = call('/admin')
            assert status == 200 and b'BUILD 42' in body and 'Content-Security-Policy' in headers
            otp = json.loads(call('/v1/auth/request-otp', {'phone': '6045550123'})[2])
            account = json.loads(call('/v1/auth/verify-otp', {'challengeId': otp['challengeId'], 'code': otp['developmentCode']})[2])
            token = account['accessToken']
            assert json.loads(call('/v1/passenger/me', token=token)[2])['id'] == account['passenger']['id']
            process.terminate(); process.wait(10)
            process = start()
            assert json.loads(call('/v1/passenger/me', token=token)[2])['id'] == account['passenger']['id']
            print('PASS: two-worker Gunicorn HTTP health, Admin CSP, sign-in, authenticated access and persisted session after process restart (SQLite).')
        finally:
            process.terminate(); process.wait(10)


if __name__ == '__main__': main()
