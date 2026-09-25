# Safe database migration to Build 40

Build 40 uses additive SQLite setup and does not require a blank database. Never test against your only copy.

1. Stop every old backend process.
2. Back up the entire existing project/database.
3. Run:

```powershell
python MIGRATE_DATABASE_BUILD_40.py --source "G:\RideNova\data\existing.sqlite3" --destination "G:\RideNova\data\ridenova-build40.sqlite3"
```

4. The script uses SQLite backup, initializes Build 40 tables on the destination only, checks required tables and `PRAGMA integrity_check`, and prints preserved ride/passenger/driver counts.
5. Start Build 40 with `--database` pointing to the destination copy.
6. Compare accounts, rides, drivers and staff and complete the manual checklist.
7. Only after acceptance should the copy become active. Keep the original rollback copy.

The script refuses to overwrite an existing destination. Owner credentials are created only if both explicit bootstrap variables are present and the staff table is empty.

