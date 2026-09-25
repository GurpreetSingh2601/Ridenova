"""Run the portable Build 40 verification suite (Python 3.11+ and Node.js)."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def run(*command):
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    run(sys.executable, 'RUN_TESTS.py')
    run(sys.executable, 'verification/admin-preflight.py')
    run('node', 'verification/admin-source-test.cjs')
    run(sys.executable, 'verification/android-source-preflight.py')
    print('\nPASS: portable Build 40 verification completed.')
    print('Android Gradle compilation and physical-device checks remain separate acceptance steps.')


if __name__ == '__main__':
    main()
