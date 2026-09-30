"""Portable regression checks; PostgreSQL and Android compilation are separate gates."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    node = shutil.which('node')
    if not node:
        raise SystemExit('Node.js not found. Install Node LTS and open a new PowerShell window. Verify node --version there.')
    commands = [(sys.executable, 'RUN_TESTS.py'), (sys.executable, 'verification/admin-preflight.py'),
                (node, 'verification/admin-source-test.cjs'), (sys.executable, 'verification/android-source-preflight.py')]
    for command in commands:
        print('\n> ' + ' '.join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    print('PASS: portable Build 42 checks. PostgreSQL integration, Android compilation and deployed network testing are separate requirements.')


if __name__ == '__main__': main()
