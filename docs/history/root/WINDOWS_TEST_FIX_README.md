RideNova Build 25 - Windows SQLite test cleanup fix

Problem: Windows WinError 32 when a test's TemporaryDirectory deletes test.db.
Cause: Python sqlite3.Connection's default with-statement commits or rolls back but does not close the connection.
Fix: backend/server.py now creates a ClosingConnection that closes after commit/rollback when a with block exits.

This ZIP is the complete Build 25 with the targeted server.py modification. Preserve your current Gradle settings and development database. Do not delete or overwrite your existing database.

Alternative: From this ZIP, copy ONLY RideNovaPassenger_v0_23_Build23_Major/backend/server.py over the matching file in your existing project.

Run tests from the RideNovaPassenger_v0_23_Build23_Major directory:
python -m unittest discover -s backend -p "test_*.py"

Validation: 50 tests passed on Linux; please verify on Windows as well.
