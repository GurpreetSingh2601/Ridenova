"""Dependency-free Build 42 Admin HTML structure and JavaScript syntax preflight."""
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import tempfile
import shutil


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'Passenger' / 'backend' / 'admin' / 'index.html'


class AdminParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.scripts = []
        self._script = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get('id'):
            self.ids.append(values['id'])
        if tag == 'script' and not values.get('src'):
            self._script = []

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self._script is not None:
            self.scripts.append(''.join(self._script))
            self._script = None


def main():
    node = shutil.which('node')
    if not node:
        raise SystemExit('Node.js was not found in this terminal PATH. Install Node LTS, reopen the terminal, then run node --version. You can run verification from Windows PowerShell outside Android Studio.')
    source = HTML.read_text(encoding='utf-8')
    parser = AdminParser()
    parser.feed(source)
    parser.close()
    required = {
        'ops-nav', 'staff-workspace', 'audit-workspace', 'staff-create-form', 'staff-login',
        'refresh', 'rides', 'fleet-rows', 'support-rows', 'staff-rows', 'audit-rows'
    }
    # ops-nav is created by JavaScript; all other required nodes must exist in source markup.
    missing = (required - {'ops-nav'}) - set(parser.ids)
    assert not missing, f'Missing Admin nodes: {sorted(missing)}'
    duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
    assert not duplicates, f'Duplicate Admin IDs: {duplicates}'
    for text in ('Dashboard', 'Rides', 'Drivers / Fleet', 'Support', 'Finance',
                 'Staff & Access', 'Audit Logs', 'BUILD 42', 'ADMIN v0.9.1'):
        assert text in source, f'Missing Admin navigation/release label: {text}'
    assert 'BUILD 35 · ADMIN' not in source.upper()
    assert 'window.loadPagedRides=async function' in source
    assert "const staffWorkspace=document.getElementById('staff-workspace');if(staffWorkspace)" in source
    assert len(parser.scripts) == 7, f'Expected 7 inline scripts, found {len(parser.scripts)}'
    with tempfile.TemporaryDirectory() as directory:
        for number, script in enumerate(parser.scripts, 1):
            path = Path(directory) / f'admin-script-{number}.js'
            path.write_text(script, encoding='utf-8')
            subprocess.run([node, '--check', str(path)], check=True)
    print('PASS: Admin HTML IDs/navigation are complete and all 7 shipped inline scripts pass Node syntax checks.')


if __name__ == '__main__':
    main()
