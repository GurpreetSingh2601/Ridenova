# RideNova Build 29

Passenger **0.25.0-build29** · Driver **0.10.0-build29** · Admin **0.2** · shared API **29.0**

This is a substantial **development source release**, continuing the supplied Build 28 ZIP. It connects the Android Driver app to individual fleet accounts and the existing Passenger ride records. The two Android project folder names are retained so existing Android Studio projects and setup instructions remain recognizable. Their app version labels are updated.

Read `VERIFICATION.md` for exactly what was tested and what still requires phones. This is not a production launch bundle. Payments remain simulated; document approval is a sample review workflow, not identity or legal verification.

## What is new

- Individual driver registration and access restoration in Android; per-install credentials encrypted with Android Keystore and excluded from backup.
- One shared dispatch/ride lifecycle: nearest eligible driver, category matching, 20-second offer leases, decline cooldowns, stale-GPS exclusion, acceptance, live position, arrival, passenger PIN, completion, cancellation/reassignment, recovery and per-driver trip/earnings history.
- Passenger availability reads the fleet; fleet driver details match the existing Passenger parser.
- Android document picker: PDF, PNG or JPEG up to 2 MiB, expiry, review status and rejection reason. Four current approved documents plus driver approval are required for dispatch.
- Admin v0.2: searchable fleet, document downloads, approve/reject with notes, driver approval/suspension, credential reset, audit trail and fleet CSV export. Existing trip and earnings views remain.
- Profile edits save to the server and trigger renewed review. Active trips block profile/document replacement and credential reset.
- Additional reliability: idempotent lifecycle retries, PIN attempt limits, expired-offer reassignment even if the original phone disappears, cross-system offer exclusion, stationary GPS updates, server-side offline reconciliation, and safe handling of history refresh errors.
- Restored Gradle wrappers and root-level server/test launchers.

## 1. Keep your existing data and configuration

1. Extract this ZIP into a **new** folder; keep Build 28 as a backup.
2. Stop the old backend. Back up your database before starting Build 29. To retain passengers/trips/accounts, use your existing `ridenova-dev.sqlite3` via `--database` or copy it into the Passenger project. Do not run two servers against the same test database.
3. Copy your own Maps key and SDK path settings into each project's `local.properties`; retain your own backend origin if different. No personal keys, credentials, database or signed APK is included.
4. The supplied backend is SQLite. It does not migrate a separately customized MySQL backend.

Migration adds document columns and fleet support tables without dropping existing ride, passenger or fleet data. Existing Build 28 fleet drivers must submit and obtain approval for all four documents before receiving new rides. Existing assigned fleet rides remain recoverable.

## 2. Start the shared backend (Windows PowerShell)

From the extracted Build 29 root:

```powershell
$env:RIDENOVA_DEV_ADMIN_TOKEN = "replace-with-your-own-long-private-test-token"
python START_SERVER.py
```

To use a database kept elsewhere:

```powershell
python START_SERVER.py --database "G:\RideNova\ridenova-dev.sqlite3"
```

Open `http://127.0.0.1:8080/health` and check `version: 29.0`. Open `http://127.0.0.1:8080/admin`, enter your admin token and load the dashboard. The admin token belongs on your laptop, **not** inside either Android app. The server listens on loopback only.

## 3. Connect each test phone

```powershell
adb devices
adb -s YOUR_PASSENGER_DEVICE_SERIAL reverse tcp:8080 tcp:8080
adb -s YOUR_DRIVER_DEVICE_SERIAL reverse tcp:8080 tcp:8080
adb -s YOUR_SECOND_DRIVER_DEVICE_SERIAL reverse tcp:8080 tcp:8080
```

Use each device's actual serial, including its wireless-debugging serial if applicable. Repeat `adb reverse` after reconnecting/rebooting phones. Each phone can then reach the laptop at `http://127.0.0.1:8080`.

## 4. Build the Android apps

Open the retained Passenger and Driver project folders separately in Android Studio. Use the compatible Gradle JDK (17 or the IDE's supported bundled JDK), sync, and install Debug on your test devices. Install SDK/build tools when prompted. Both projects include `gradlew`, `gradlew.bat` and the wrapper JAR.

Passenger `gradle.properties` includes:

```properties
RIDENOVA_API_BASE_URL=http://127.0.0.1:8080
```

Driver `local.properties`:

```properties
MAPS_API_KEY=YOUR_EXISTING_MAPS_KEY
RIDENOVA_DEV_URL=http://127.0.0.1:8080
```

Keep your existing `sdk.dir` entry and Passenger Maps key configuration. The same Driver build supports multiple phones; each registers its own account. **Do not copy one driver credential onto multiple different drivers' phones.** Fleet mode is the default even if an old `RIDENOVA_DEV_TOKEN` remains in local.properties.

Legacy single-driver testing remains available only by explicitly adding `RIDENOVA_LEGACY_DRIVER=true` and the old development token. Use it to finish old legacy rides if necessary, then remove that flag and register fleet drivers. Offers are excluded across both dispatch systems.

## 5. Onboard two drivers

1. Open Driver on each phone; enter a name, vehicle, plate and category. Use sample information.
2. Open **Account → Onboarding & documents**. Upload sample Licence, Insurance, Registration and Inspection files with current/future expiry dates.
3. In Admin, refresh fleet and select **Review**. Download/inspect each sample document, then approve or reject it. Rejections require a reason; the driver sees that reason and can replace the file.
4. Approve the driver after all four documents are approved. Refresh Driver status, allow location, and go online. A fresh GPS fix is needed before dispatch.
5. Book in Passenger using the same category. The nearest eligible available driver receives the offer. A reserved driver is unavailable to other bookings until the offer expires/declines or the trip finishes.
6. Accept, arrive, enter the Passenger's PIN, start and complete. Check Passenger history, the accepting driver's history and Admin earnings. The other driver must not see this trip in their history.

Sample file checks validate size, media signature, expiry and revision. They do **not** check the truth of a document or perform malware scanning. Use sample files only in this local development workflow.

## Access recovery and operational behavior

- Lost/reinstalled phone: Admin **Reset lost driver access** invalidates the old credential and takes the driver offline. Copy the new test credential privately to **Restore access** on the Driver entry screen. For an app still holding the revoked credential, clear its app storage in Android Settings to return to that screen. Server history remains available after restoration. Reset is blocked during an active ride.
- Profile changes take the driver offline, mark uploaded documents pending again, and require admin approval. They do not remove suspension.
- Replacing a document takes the driver offline until the replacement is approved. It cannot be done during an active trip. Expired documents block new dispatch.
- Suspending a driver blocks new requests immediately. An already accepted trip can still share GPS and finish, so the passenger is not stranded by a mid-trip status change.
- Five wrong PIN attempts lock further start attempts for one minute.
- Driver cancellation before trip start requeues the ride and clears the previous driver/PIN. Cancellation after trip start is rejected.
- Admin keeps its token only in page memory. Refresh manually for current fleet state.

## Tests

From the Build 29 root, run `python RUN_TESTS.py`. Android build commands are `gradlew.bat :app:assembleDebug :app:lintDebug` from each Android project. Review `VERIFICATION.md` and `DEVICE_ACCEPTANCE.md` before treating this as validated on your devices.

All older START_HERE files describe historical builds. This file is authoritative for Build 29.
