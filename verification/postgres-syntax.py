"""Parse migrations and SQL exercised by SQLite tests with PostgreSQL's parser.
Requires pglast. This catches syntax errors, NOT PostgreSQL execution/type/locking errors.
"""
import re
import ast
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Passenger/backend'))
sys.path.insert(0, str(ROOT / 'Passenger'))
from pglast import parse_sql
import database

seen = set()
execute = database.ClosingConnection.execute


def checked(self, statement, parameters=()):
    if re.match(r'^\s*(SELECT|INSERT|UPDATE|DELETE|BEGIN IMMEDIATE)\b', statement, re.I):
        translated = database.translate(statement).replace('%s', 'NULL')
        if translated not in seen:
            parse_sql(translated)
            seen.add(translated)
    return execute(self, statement, parameters)


if __name__ == '__main__':
    for migration in sorted((ROOT/'Passenger/backend/migrations').glob('*.sql')):
        parse_sql(migration.read_text())
        print('Parsed migration:', migration.name, flush=True)
    for module in ('operations.py', 'migrate.py', 'tools/import_sqlite.py', 'tools/backup_restore.py'):
        tree = ast.parse((ROOT/'Passenger/backend'/module).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'execute' and node.args:
                argument = node.args[0]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str) and re.match(r'^(SELECT|INSERT|UPDATE|DELETE|CREATE|SET)', argument.value):
                    parse_sql(argument.value.replace('%s', 'NULL'))
        print('Parsed constant operations SQL:', module, flush=True)
    database.ClosingConnection.execute = checked
    suite = unittest.defaultTestLoader.discover(str(ROOT/'Passenger/backend'), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print('Parsed', len(seen), 'distinct executed domain statements. PostgreSQL execution still required.')
    raise SystemExit(0 if result.wasSuccessful() else 1)
