# RideNova v0.19 — Authentication and passenger profile

## What changed

- Canadian `+1` phone entry and backend OTP challenge.
- The local development code is **246810** and is shown on the OTP screen. No SMS is sent. This tests the account flow but does not verify ownership of a real phone.
- A phone number maps to one persistent backend passenger account.
- Access tokens expire after 15 minutes; refresh tokens last 30 days and rotate automatically.
- Android encrypts tokens with an app-private Android Keystore AES-GCM key.
- Signed-in passengers reopen directly into RideNova. An incomplete account reopens profile setup.
- Passenger name and optional email are stored on the server. The Account screen can edit them.
- Sign out revokes the current server session, removes the encrypted local tokens, and clears passenger information, recent places and saved Home/Work from this device. Server profile and trips remain for the next sign-in.
- On the first v0.19 sign-in, rides belonging to the phone's current legacy v0.18 device session are migrated into the account.
- All v0.18 scheduled-ride, fare/GST, one-recent-destination and map-padding improvements remain.

## Install the Android app

1. Extract this ZIP to a new folder and keep your working v0.18 folder as backup.
2. Open `RideNova_v0_19`, which contains `settings.gradle.kts`.
3. Copy your private `local.properties` from v0.18 so Android Studio can find the SDK and Maps key. This ZIP intentionally excludes it.
4. Sync and Run. Version is **0.19.0**, versionCode **21**. Package ID and dependency/SDK versions remain unchanged.

The supplied project lineage does not contain a complete command-line Gradle wrapper. Continue using the Gradle setup that already works in your Android Studio.

## Backend mode: required to test accounts

Stop the v0.18 server. Back up its SQLite database, then run the v0.19 server with that same file if you want to keep and migrate prior development rides:

```powershell
py -3 -m unittest discover -s backend -v
py -3 backend/server.py --database "G:\your-existing-folder\ridenova-dev.sqlite3"
```

Replace the path with the database you actually used. If you omit `--database`, a new `ridenova-dev.sqlite3` is created in the terminal's current folder. Health check http://127.0.0.1:8080/health should report `0.19.0` and `development-otp`.

For a USB-connected Pixel, keep the server running, execute `adb reverse tcp:8080 tcp:8080`, and put this in `gradle.properties`:

```properties
RIDENOVA_API_BASE_URL=http://127.0.0.1:8080
```

Then Sync and rebuild the debug app. For the standard emulator, use `http://10.0.2.2:8080`. Only debug loopback/emulator connections allow cleartext HTTP. This server binds to your computer's loopback address and must not be exposed publicly.

## Account test walkthrough

1. Start v0.19 with your v0.18 database and open the v0.19 app without clearing its data.
2. Enter a ten-digit Canadian-format number. The local server accepts structurally valid NANP numbers; use a reserved/test number and do not enter another person's number.
3. On the next screen, enter the displayed development code **246810**. A code lasts five minutes, permits five wrong attempts and cannot be reused. Wait one minute before requesting another.
4. Complete first name, last name and optional email. The verified phone field cannot be edited from Profile.
5. Book or schedule a development ride. Confirm that Trips reload after restarting the app.
6. Edit the profile in Account and restart the app to verify the server value returns.
7. Sign out. Local passenger data disappears. Sign in with the same phone and code; the profile and server rides return.
8. Leave the app open longer than 15 minutes, then load Trips. The access token should refresh automatically without asking for another OTP.

Use one account per test phone. The OTP screen reveals the code, so anyone with local access can sign in as any structurally accepted test number. This is intentional for local development and unacceptable for public use.

## Offline mode

If `RIDENOVA_API_BASE_URL` is absent, RideNova keeps the existing offline prototype and uses code **123456**. Offline profiles and trips remain local. They are separate from backend passenger accounts except for the one-time legacy migration performed when the same installed app later signs into the v0.19 backend.

## Validation and current limits

38 backend tests pass: the 29 v0.18 booking/scheduling checks plus nine authentication tests for phone validation, rate limiting, code expiry/reuse/attempt limits, account reuse, profile validation, access expiry, refresh rotation, logout and legacy-ride migration. Nine Java scheduling/date-time checks also pass.

The Android app could not be compiled in this workspace because Android SDK/Gradle are unavailable. Its source and navigation paths were inspected, and the pure Java scheduling helper still compiles under JDK 17. Build and test on your Pixel before continuing.

Test these Android cases: new account, existing account, wrong/expired code, rapid resend, server offline, app restart, access refresh, incomplete profile restart, profile update, logout, v0.18 ride migration and sign-in with a different test phone.

This release has no SMS delivery, real proof of phone ownership, Google/Apple sign-in, phone change, account deletion, profile-photo upload or remote saved-place sync. OTP abuse protection is local-development grade. Authentication must be upgraded before any public deployment. Real payments and driver dispatch are still disconnected.

API details are in `backend/API_CONTRACT.md`. The earlier `START_HERE_v0_18.md` is retained as historical setup; its anonymous passenger-session description is superseded by v0.19.
