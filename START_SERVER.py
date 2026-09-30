"""Build 42 loopback development launcher for the one shared RideNova backend."""
from pathlib import Path
import os
import subprocess
import sys
root=Path(__file__).resolve().parent/'Passenger'
if not os.environ.get('RIDENOVA_DEV_ADMIN_TOKEN'):
    raise SystemExit('Set RIDENOVA_DEV_ADMIN_TOKEN to a private test value before starting. See START_HERE_BUILD_41.md.')
raise SystemExit(subprocess.call([sys.executable,'backend/server.py',*sys.argv[1:]],cwd=root))
