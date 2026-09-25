# RideNova Build 41 — staging infrastructure candidate

This is one consolidated source package, based on the accepted Build 40.1 tree.
**Build 41 is not yet an accepted, deployed milestone.** PostgreSQL execution,
Android compilation, authorized Render deployment and separate-network device
testing are release gates. See `TEST_RESULTS_BUILD_41.md` for actual evidence.

## What is included

| Component | Version / location |
|---|---|
| Passenger | 0.33.0-build41, code 43 — `Passenger/` |
| Driver | 0.18.0-build41, code 39 — `Driver/` |
| Shared API | 41.0 — `Passenger/backend/` |
| Admin | 0.8.0 — same API, `/admin` |

The scheduler is a worker of this same backend. There is no second Driver API.
No payment processor, SMS provider, real payout or public launch is enabled.

## Start safely

1. Extract the ZIP directly into `G:\RideNova` or `C:\RideNova`. Its short root is `RN41`.
2. Keep your accepted Build 40 folder and existing database. No database is shipped.
3. Read `DEPLOYMENT_AND_MIGRATION_BUILD_41.md` before moving any data or creating cloud services.
4. Local development continues to use SQLite and the debug Android variants.
5. Staging variants use HTTPS, separate application IDs and separate local storage.

From the extracted root, run portable verification in a terminal where Node works:

```powershell
node --version
python VERIFY_BUILD_41.py
```

These checks use disposable databases; they do not need your server running.
They do not substitute for the PostgreSQL suite or Android compilation.

To validate a separate local database copy:

```powershell
python MIGRATE_SQLITE_COPY.py --source "G:\RideNova\data\ridenova.sqlite3" --destination "G:\RideNova\data\ridenova-build41-copy.sqlite3"
python START_SERVER.py --database "G:\RideNova\data\ridenova-build41-copy.sqlite3"
```

Stop the old backend before copying. Keep your existing local environment values
for Owner/development access. The copied database retains existing accounts.
For local Android debug builds, keep the known working Maps settings and API URL.

## Staging Android builds (after deployment)

In **both** projects' `gradle.properties`, set the same real origin:

```properties
RIDENOVA_STAGING_API_BASE_URL=https://YOUR-APP.onrender.com
```

Open each project separately in Android Studio and select `staging`, or run:

```powershell
.\gradlew.bat assembleStaging
```

No real URL is embedded in this package. A missing/HTTP staging URL fails the
build. Staging uses the debug signing certificate for controlled distribution,
but disables debugging and cleartext traffic. Production release builds are
deliberately gated. Add these Maps API Android restrictions with the signing SHA-1:

- `com.ridenova.passenger.staging`
- `com.ridenova.driver.staging`

Staging apps appear as **RideNova Staging** and **RideNova Driver Staging** and
coexist with local apps. Sign in again; local bearer sessions do not migrate.
Passenger testers receive an invitation code privately (no SMS). Drivers are
provisioned by the administrator; self-registration/recovery remains local-only
until real phone verification is implemented. Password sign-in, documents,
approval, ride eligibility, dispatch, trips and support remain available.

## Next acceptance step

Use the single checklist in `MANUAL_TEST_CHECKLIST_BUILD_41.md` once CI is green
and deployment is authorized. The Render proposal is in
`DEPLOYMENT_AND_MIGRATION_BUILD_41.md`; no services have been created or charged.

Build 40 documents/test logs are retained under `docs/history/build40/` as
historical evidence. Their old versions and commands are not Build 41 instructions.
