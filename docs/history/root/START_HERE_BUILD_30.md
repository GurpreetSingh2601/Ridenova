# RideNova Build 30 — Driver accounts

Passenger **0.26.0-build30** · Driver **0.11.0-build30** · Admin **0.3** · API **30.0**

This continues Build 29 with driver username/password sign-in, logout, account switching and recovery. Existing multi-driver dispatch, documents, Admin, Passenger and shared-backend features remain. The Android project folder names are intentionally retained.

**One backend server. One existing database. No Windows administrator privileges required.**

## Upgrade without losing your accounts

1. Extract into a new folder and keep Build 29 as a backup.
2. Stop the old backend and back up the database you currently use.
3. Keep your existing Maps keys, SDK path and backend origin in the two Android projects. Do not copy build caches from the old projects.
4. Start this backend with the **same SQLite database path**. It adds two sign-in tables without deleting existing accounts, documents or trips. This does not migrate a separate custom MySQL server.
5. Build/install both updated Debug apps using Android Studio. See `VERIFICATION.md`: Android compilation and device execution were **not reverified** in this session.

## Start the server — choose ONE method

### Keep your familiar command

From the Passenger project folder, in an ordinary PowerShell window:

```powershell
$env:RIDENOVA_DEV_ADMIN_TOKEN = "your-own-long-private-test-token"
python backend/server.py --database "G:\RideNova\your-existing-database.sqlite3"
```

Replace the example database path with the file you already use.

### Or use the convenience launcher

From the extracted Build 30 root:

```powershell
$env:RIDENOVA_DEV_ADMIN_TOKEN = "your-own-long-private-test-token"
python START_SERVER.py --database "G:\RideNova\your-existing-database.sqlite3"
```

Both commands launch the **same** shared server on `http://127.0.0.1:8080`. Do not run both. The admin token is the dashboard password, not Windows administrator access.

Check `/health` for `version: 30.0`. Open `/admin` in your laptop browser to use Admin v0.3. The server remains loopback-only and development-only.

## Existing Build 29 driver: add sign-in once

If Driver is still signed in after the upgrade:

1. Open **Account → Sign-in & logout**.
2. Choose a username and password; confirm the password and press **Save sign-in details**.
3. Your existing driver ID, approval, documents and trip history remain the same.
4. You can now use **Log out / switch account** and sign in again with those details.

Choose a username of 3–40 letters/numbers/dots/underscores/hyphens. Usernames are case-insensitive. Passwords are case-sensitive, 10–128 characters, and are not trimmed. The server stores salted password hashes; the phone stores only an encrypted session credential.

Older accounts must set sign-in details before logout so they can return to the same account. Do not create a duplicate account to retain an existing driver's history.

## New driver / switching accounts

The entry screen offers **Sign in** and **Create account**. Registration collects username/password plus name, vehicle, plate and category. New drivers still need document review and admin approval before receiving rides.

To switch drivers on one phone:

1. Finish or cancel the active trip.
2. **Account → Sign-in & logout → Log out / switch account**.
3. Confirm logout, then sign in as the other driver or create another account.

No Android Clear storage step is needed. Logout takes the driver offline, releases pending offers, revokes the session, stops the phone's location service and clears cached profile/trip data. Server history and documents remain. The new account gets a fresh UI state and its own server data.

Logout requires reaching the backend. If the server is unavailable, the app keeps the session and shows an error so it does not falsely claim to have taken the driver offline. An already-revoked session can be cleared from the account screen. A lost logout response is safe to retry.

**Logout is blocked during an accepted/arrived/started trip.** Driver cancellation remains available only before the trip starts. Once a trip starts, complete it before signing out.

One phone is enough for sequential account testing. Two separate installations (phone + emulator, or two phones) are needed to test two drivers online simultaneously.

## Sign-in on another device and recovery

- A successful sign-in replaces that driver's previous session. Idle drivers start offline. An active ride remains recoverable on the newly signed-in device. Do not share an account between different drivers.
- Five failed attempts lock sign-in for that username for one minute. Successful sign-in clears failed attempts.
- Forgot password or lost the old Build 29 credential: ask your Admin to open the driver review and choose **Reset lost driver access**. This takes the driver offline and revokes the old session; for accounts with a password, that password cannot sign in until recovery is completed.
- Admin shows the username in the fleet table. On the Driver entry screen, choose **Forgot password / recover an older account**, enter the existing username, the recovery credential and a new password. Accounts that never configured a username can choose one here.
- The recovery credential is replaced after use. Reset is blocked during active rides. Suspended accounts can recover/sign in, but cannot go online until approved.

## Phone connection and Maps setup

Keep the same setup as Build 29:

```powershell
adb devices
adb -s YOUR_PHONE_SERIAL reverse tcp:8080 tcp:8080
```

Repeat for each phone/emulator. Driver uses `RIDENOVA_DEV_URL=http://127.0.0.1:8080` in `local.properties` (also the Debug default), plus your Maps key. Passenger uses `RIDENOVA_API_BASE_URL=http://127.0.0.1:8080` in `gradle.properties` and its existing Maps configuration.

Remove `RIDENOVA_LEGACY_DRIVER=true` if you previously enabled single-driver compatibility mode. Login/logout applies to the fleet mode, not the optional older demo/legacy mode.

## Verification folder

**You do not need to run or change anything in `verification` to use RideNova.** It contains test records and optional developer test scripts. Files marked historical are Build 29 evidence, not Build 30 results.

For current results, read `VERIFICATION.md`. Backend tests: `python RUN_TESTS.py`. Optional Android checks on your configured Windows development machine: `powershell -File VERIFY_ANDROID.ps1`. Physical-device checks are in `DEVICE_ACCEPTANCE.md`.

This remains a local development release: use sample documents and test data. Password sign-in does not verify real-world identity; payments/payouts and production hosting remain outside this release. Earlier START_HERE files are historical; this file is authoritative.
