# Start here — RideNova Build 40

Windows verifier correction included: see `WINDOWS_VERIFICATION_FIX.md` for the
WinError 10053 regression-test fix and one-file update instructions.

Booking correction included: read `BOOKING_FIX_BUILD_40.md`. Rebuild Passenger
to resolve Confirm HTTP 413 and the literal `null` route warning. Build 40 is
still awaiting Android compilation/device acceptance.

Consolidated source versions: Passenger Android `0.32.1-build40`, Driver Android `0.17.0-build40`, shared API `40.0`, Admin `0.7.0`.

This is not a public-production release. Payments, SMS, identity verification and payouts are simulated. Build 41 is the planned infrastructure milestone and requires separate authorization.

## Protect and migrate your database

Do not copy a blank database over your current one. Stop the old server and create a validated copy:

```powershell
python MIGRATE_DATABASE_BUILD_40.py --source "G:\RideNova\data\existing.sqlite3" --destination "G:\RideNova\data\ridenova-build40.sqlite3"
```

The utility refuses to overwrite the destination, uses SQLite backup, runs additive setup only on the copy and checks integrity. Keep the original until acceptance is complete. See `DATABASE_MIGRATION_BUILD_40.md`.

## Start the one shared backend

Python 3.11+ is required:

```powershell
$env:RIDENOVA_DEV_ADMIN_TOKEN="a-long-private-development-token"
python START_SERVER.py --database "G:\RideNova\data\ridenova-build40.sqlite3"
```

Check `http://127.0.0.1:8080/health` for build `40`. Admin is at `http://127.0.0.1:8080/admin`.

For a physical USB Android device:

```powershell
adb reverse tcp:8080 tcp:8080
```

Passenger `gradle.properties`:

```properties
RIDENOVA_API_BASE_URL=http://127.0.0.1:8080
```

Driver `local.properties`:

```properties
RIDENOVA_DEV_URL=http://127.0.0.1:8080
MAPS_API_KEY=YOUR_ANDROID_MAPS_KEY
```

Use Driver sign-up/sign-in; do not enable the legacy shared Driver token unless deliberately testing compatibility.

## Verify and build

```powershell
python VERIFY_BUILD_40.py
cd Passenger
gradlew.bat clean assembleDebug
cd ..\Driver
gradlew.bat clean assembleDebug
```

The portable suite passed on the packaged source. Android Gradle compilation was blocked in the packaging environment because Gradle 9.6 could not be downloaded, so both Android commands remain required on your Windows machine.

Read `RELEASE_NOTES_BUILD_40.md`, `TEST_RESULTS_BUILD_40.md`, `MANUAL_TEST_CHECKLIST_BUILD_40.md`, `KNOWN_ISSUES_BUILD_40.md`, and `STAFF_PERMISSIONS_AND_TESTING.md` next.
