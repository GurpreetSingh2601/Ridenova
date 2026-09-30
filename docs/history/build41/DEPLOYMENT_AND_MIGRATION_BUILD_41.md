# Build 41 deployment, data preservation and recovery

Status: implementation candidate; no cloud resources deployed. The PostgreSQL
integration/restore suite and both Android compilations must pass before deployment.

## Concrete Render proposal — approval required before creation

| Resource | Proposed configuration | Planning estimate (USD/month) |
|---|---|---:|
| Shared API + Admin | Oregon, 0.5 CPU / 512 MB, two Gunicorn workers | $7 |
| Same-backend scheduler | Oregon, 0.5 CPU / 512 MB | $7 |
| PostgreSQL | Oregon, PostgreSQL 16, 0.1 CPU / 256 MB | $6 + storage |

Estimated base compute: **US$20/month**, plus 1 GB database storage, bandwidth,
build usage, applicable taxes and any selected workspace plan. This is a planning
estimate, not an account quote or spending cap. Recheck the Render checkout total
before approval. Restore drills can temporarily require a second paid database.
No Redis, separate Driver backend, payment service or custom domain is required.

`render.yaml` declares these exact three resources and disables automatic deploys.
PostgreSQL external access is closed (`ipAllowList: []`). Oregon stores data in
the USA; this is **not Canadian data residency**. Use synthetic/invited test data
until the owner approves the region and appropriate privacy review is complete.

Official references checked September 2026:
- https://render.com/pricing
- https://render.com/docs/compute-plans
- https://render.com/docs/blueprint-spec
- https://render.com/docs/regions
- https://render.com/docs/postgresql-backups
- https://render.com/docs/deploy-hooks

## Configuration and secrets

Examples are in `config/`; they are documentation, not an automatically loaded
`.env` file. Enter real values in Render secret settings. Keep development,
staging and eventual production in distinct databases, service configurations
and app variants. Production startup intentionally fails until later launch gates.

- `DATABASE_URL`: private Render connection string, shared by API and scheduler.
- `RIDENOVA_PUBLIC_ORIGIN`: exact HTTPS API origin, no path, credentials or query.
- `RIDENOVA_STAGING_TESTERS`: JSON map of invited +1 passenger numbers to individual,
  randomly assigned six-digit codes. Supply each code privately; never place real
  values in source, issue descriptions or logs. These are test credentials, not SMS proof.
- `RIDENOVA_STAGING_DRIVER_PHONES`: comma-separated invited canonical +1 numbers.
- `RIDENOVA_RATE_SECRET`: generated random secret, at least 32 characters.
- `FORWARDED_ALLOW_IPS=*`: only for Render's proxy-isolated listener. Never expose
  that HTTP listener directly; use actual proxy ranges when porting elsewhere.

No shared development Admin/Driver tokens are accepted in staging. Existing staff
roles remain server-enforced. API logs omit bodies, coordinates, phone numbers,
tokens, IPs and query strings. Restrict access/retention to platform logs as well.
Do not store real card numbers or real verification documents in this test system.

## Verification before initial deployment

Commit this source to an owner-controlled private repository. The included GitHub
workflow runs portable tests, a two-worker HTTP smoke test, PostgreSQL concurrency/
import/restore tests, and debug/staging Android compilation. CI has not been run
from this workspace. Configure required checks and a protected `staging` environment
with owner approval; workflow YAML alone does not configure branch protections.

For local PostgreSQL verification, provision two **disposable** PostgreSQL 16 databases
named `ridenova_test` and `ridenova_restore_test`, install requirements plus PostgreSQL
16 client utilities, set `RIDENOVA_TEST_DATABASE_URL` and
`RIDENOVA_TEST_RESTORE_DATABASE_URL`, then run:

```text
python verification/postgres-integration.py
```

This suite clears test tables and recreates the restore test schema. It refuses
database names without `_test`; never point test variables at valuable databases.

## Initial deployment sequence (after explicit authorization)

1. Review Blueprint resource costs/region and required CI results before creating services.
2. Configure the secrets. The web pre-deploy step runs `python migrate.py`; it does
   not create an Owner or overwrite any data. Migrations are transactional,
   checksum-checked and protected against concurrent migration runners.
3. Keep testers out during setup. The worker may need restarting after the first
   schema migration because services initially start independently.
4. For an imported database, perform the empty-target import below **before** Owner
   bootstrap or worker heartbeat writes. Suspend API/worker while importing.
5. For a new synthetic-data staging database, run `python tools/bootstrap.py owner`
   in a private server shell. Credentials are prompted, not logged. For an imported
   database, use the preserved existing Owner account instead; bootstrap refuses
   to overwrite staff.
6. Provision invited test Drivers with `python tools/bootstrap.py driver`; review
   their sample documents and approve them in Admin. Eligibility is still admin-controlled.
7. Start/restart both services from the same commit. Confirm `/health` is live and
   `/ready` returns 200. Readiness checks migration checksums, active Owner presence,
   a scheduler heartbeat under 45 seconds old and matching API/worker commit.
8. Run `python verification/staging-smoke.py https://YOUR-APP.onrender.com`.
9. Build both Android staging variants for that URL and complete the device checklist.

Admin is served by the shared API at `/admin`; it needs no separate hosting.

## SQLite → PostgreSQL without overwriting your database

The importer supports the accepted Build 40 schema. Unknown/missing tables or
columns cause rejection rather than silently losing data. Older copies should
first be upgraded with `MIGRATE_SQLITE_COPY.py` and reviewed locally.

1. Stop the old API and prevent bookings during cutover. Back up the original
   SQLite database using the provided copy tool; retain it offline unchanged.
2. Validate a representative copy in the disposable PostgreSQL test environment
   first. Do not upload genuine passenger/driver data as a rehearsal.
3. Provision an empty target and run `python migrate.py` with `DATABASE_URL` set
   privately. Keep API and scheduler stopped: even heartbeat/rate-limit rows make
   the importer refuse a nonempty target.
4. With the accepted SQLite copy available in a private shell, run from `Passenger/backend`:

```text
python tools/import_sqlite.py /private/path/ridenova-copy.sqlite3 --confirm-offline --report /private/path/import-report.json
```

The source opens read-only and is snapshotted using SQLite's backup API. The tool
checks integrity and foreign keys, imports all 31 domain tables in one PostgreSQL
transaction, checks row counts/content hashes, and resets identity sequences.
It refuses occupied targets. A receipt is committed in `import_receipts`.
Confirm the report's actual table count; the code discovers and verifies the schema.

Accounts, salted password hashes, rides, route JSON, ratings, support, documents,
declines, audit trails and earnings remain. Deliberate environment-boundary resets:
passenger/Admin sessions and OTPs are invalidated, Driver bearer tokens are rotated
to unknown values, drivers go offline, GPS freshness and transient offers/radar
leases clear. Active ride assignments/history are preserved and recovered after
new sign-in. No new credentials are printed. Drivers must already have password
accounts with invited phone numbers; resolve any legacy token-only accounts locally
before cutover. Accounts flagged for credential recovery must be recovered locally
before import because the development recovery endpoint is disabled in staging.

Copying/importing is not continuous replication. Keep the old system stopped after
cutover; do not accept rides into two divergent databases. If validation fails,
leave the original untouched and troubleshoot the disposable target.

## Backups and restore verification

Paid Render PostgreSQL currently provides managed point-in-time recovery: Hobby
workspaces have a 3-day window; Pro and higher have 7 days. Verify this in the
actual account. That service has not been configured or exercised here.

The portable logical backup tool requires PostgreSQL 16 `pg_dump`/`pg_restore`:

```text
python tools/backup_restore.py backup /private/backups/ridenova.dump
```

It takes the API/scheduler request lock, writes a non-overwriting custom-format
dump and a row-count/content-hash manifest. Transient rate limits are excluded.
Use a short maintenance window for growing databases. Copy the dump and manifest
to encrypted, access-controlled off-host storage. The tool does not upload backups
or create storage subscriptions. Schedule retention/exports in the authorized
deployment environment; off-host automation is still an operational setup task.

Set `RESTORE_DATABASE_URL` to a separate, empty disposable database, then:

```text
python tools/backup_restore.py restore-check /private/backups/ridenova.dump
```

The tool verifies the archive checksum, refuses occupied targets, restores in one
transaction, then compares every public table's rows/content. Never restore over
a live database. Perform a restore drill before acceptance and after migration
changes; record its measured recovery time and backup age. No RPO/RTO is claimed yet.

## Monitoring, CI/CD and rollback

- `/health` is a public liveness probe; Render uses it so first-time Owner setup
  does not cause a deployment loop. It does not establish database readiness.
- `/ready` is the operational probe. Configure an external monitor after approval
  to alert after 3 failures; verify a stopped scheduler produces an alert.
- JSON logs provide request ID, HTTP status, duration and scheduler outcomes.
  Define initial alerts for elevated 5xx, missing heartbeat, DB storage/connections
  and unavailable backups. Actual account alert delivery remains to be tested.
- Automatic deploy is off. The included manual deployment workflow reruns CI,
  uses protected Render deploy hooks, deploys the verified commit, then checks
  matching API/worker readiness and smoke tests. Hooks are secrets. Do not invoke
  the workflow before deployment authorization and environment protection setup.
- Before each deployment, back up and record API/worker commit, migration checksums
  and configuration version. Deploy both services together. Migrations must be
  additive and compatible with the prior API; do not run automatic down migrations.
- If a release fails, stop new test bookings, redeploy the last compatible API and
  worker commits, and verify `/ready`, active-trip recovery and the ledger. Migration
  checksum mismatch deliberately blocks incompatible code. If a database restore
  is needed, restore to a **new** database, validate it, reconcile writes since the
  backup, then explicitly switch both services. Never silently discard later rides.

## Capacity and portability

This preserves the existing domain model: ride payloads remain JSON text and some
queries scan ride history. PostgreSQL advisory locks serialize the legacy
multi-transaction HTTP workflows across workers. This is a conservative controlled-
staging design, not a high-throughput dispatch engine. Load-test and normalize/index
hot paths before scaling. The maximum staging request rate is intentionally capped.

The Dockerfile, WSGI API, PostgreSQL migrations and worker can move to an equivalent
AWS/container environment. No AWS deployment has been attempted; proxy trust,
networking, IAM/secrets, storage and monitoring need platform-specific configuration.
