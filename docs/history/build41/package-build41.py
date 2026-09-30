"""Build the single clean RN41 source archive and verify its inventory/CRC."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / 'RideNova_Build41_Staging_Candidate.zip'
REPORT = ROOT / 'verification/build41-package-check.txt'
SUMS = ROOT / 'SHA256SUMS.txt'


def files():
    excluded = {'__pycache__', '.gradle', '.git', '.idea', 'build', 'node_modules'}
    return sorted(p for p in ROOT.rglob('*') if p.is_file()
                  and not excluded.intersection(p.relative_to(ROOT).parts)
                  and p.name not in ('local.properties', '.env', '.DS_Store')
                  and not p.name.startswith('.env.')
                  and not p.name.endswith(('.pyc', '.sqlite', '.sqlite3', '.sqlite3-wal', '.sqlite3-shm', '.db', '.jks', '.keystore', '.dump')))


def main():
    required = ['Passenger/app/build.gradle.kts', 'Driver/app/build.gradle.kts',
                'Passenger/backend/server.py', 'Passenger/backend/admin/index.html',
                'START_HERE_BUILD_41.md', 'RIDENOVA_DEVELOPMENT_RULES.md',
                'STAFF_PERMISSIONS_AND_TESTING.md', 'TEST_RESULTS_BUILD_41.md',
                'DEPLOYMENT_AND_MIGRATION_BUILD_41.md', 'render.yaml',
                '.github/workflows/verify.yml', '.github/workflows/deploy-staging.yml']
    for relative in required: assert (ROOT/relative).is_file(), relative
    assert len(list(ROOT.rglob('server.py'))) == 1, 'Expected exactly one shared backend'
    REPORT.touch(); SUMS.touch()
    included = files()
    longest = max(len('RN41/'+str(p.relative_to(ROOT)).replace('\\','/')) for p in included)
    assert longest < 200, 'Archive paths too long for short-root Windows extraction'
    REPORT.write_text(f'Build 41 staging candidate\nFiles: {len(included)}\n'
                      f'Longest archive path: {longest} characters\n'
                      'One shared backend; both Android sources; Admin; migrations; deployment workflows included.\n'
                      'Caches, local credentials, databases and signing keys excluded.\n'
                      'SHA256 inventory and ZIP CRC validated by package-build41.py.\n', encoding='utf-8')
    SUMS.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n'
                            for p in included if p != SUMS), encoding='utf-8')
    with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in included: archive.write(path, 'RN41/'+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(included)
        assert len(set(archive.namelist())) == len(included)
        assert json.loads(archive.read('RN41/release.json'))['status'] == 'staging-candidate'
        for line in archive.read('RN41/SHA256SUMS.txt').decode().splitlines():
            digest, name = line.split('  ', 1)
            assert hashlib.sha256(archive.read('RN41/'+name)).hexdigest() == digest
    print(REPORT.read_text(), end='')
    print('Archive:', OUTPUT.name, 'bytes:', OUTPUT.stat().st_size)
    print('Archive SHA256:', hashlib.sha256(OUTPUT.read_bytes()).hexdigest())


if __name__ == '__main__': main()
