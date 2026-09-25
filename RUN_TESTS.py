"""Run backend regression tests from any working directory (Python 3.11+)."""
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parent/'Passenger'
raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','backend','-p','test_*.py','-v'],cwd=root))
