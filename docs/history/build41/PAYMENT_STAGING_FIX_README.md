# Build 41 staging payment screen fix

The Passenger payment-method list used `ORDER BY rowid`. PostgreSQL has no
SQLite `rowid`, so the staging API returned a generic server error while
loading cards. `Passenger/backend/server.py` now sorts by `created_ms,id` and
allocates increasing timestamps for cards added in the same millisecond.
No schema migration or data reset is needed. Cards remain development-only
display references; no card number, CVV, or charge is processed.

## Apply

Copy the two paths in this package into the matching paths in your **current
Build 41 Git repository**. Keep your current free `render.yaml`, local
settings, database, and all other files. Then, in PowerShell at repo root:

```powershell
python RUN_TESTS.py
git add Passenger/backend/server.py verification/postgres-integration.py
git commit -m "Fix staging payment list on PostgreSQL"
git push
```

Wait for GitHub Actions `shared-api` to pass; it executes the new PostgreSQL
payment regression test in a disposable CI database. This workspace ran the
147-test SQLite/backend suite successfully but could not execute PostgreSQL
integration locally because no disposable PostgreSQL server is available.

Because the free Render Blueprint disables automatic deployment, manually
deploy the latest Git commit on `ridenova-free-trial-api` **after CI passes**.
Verify `/health` shows the new revision, then sign into Passenger Staging and
open Payment methods. The default development Visa card should load, and adding
and selecting another development display card should preserve its order.
Do not enter a real card number or CVV; actual payment processing is not in
Build 41.
