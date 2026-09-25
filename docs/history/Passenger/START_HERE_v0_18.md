# RideNova v0.18 — Scheduled rides and clearer fares

## What you can test now

- Home still shows only one recent destination; tap Search for the rest. Map padding and the location-dot improvement are retained.
- Schedule now opens real date/time pickers. Choose 15 minutes to 30 days ahead, or switch back to Ride Now.
- The screen shows the device time-zone ID and a numeric UTC offset. Clock-change gaps and repeated local times are rejected rather than silently choosing the wrong pickup instant. Keep your phone's date/time/time-zone settings current.
- Upcoming rides appear in pickup order, survive backend restarts, and can be cancelled from Upcoming. To change a pickup, cancel and book again; in-place rescheduling is not yet implemented.
- The development server checks due pickups every five seconds. Due rides enter SEARCHING with a fresh two-minute cancellation grace. No actual driver is contacted.
- If another ride is active, a scheduled ride waits; if it cannot start within 15 minutes of pickup, it moves to history as “Pickup missed · no charge.” Restarting a server also catches up or expires overdue reservations safely.
- Server fare breakdowns show subtotal, GST and total in confirmation, live ride and trip details. Offline estimates do not invent a GST breakdown.
- The confirmation page scrolls, and its Confirm button remains fixed at the bottom.

## Install in Android Studio

1. Extract the ZIP to a new folder and keep v0.17 as a backup.
2. Open `RideNova_v0_18` (the folder containing `settings.gradle.kts`).
3. Copy your own `local.properties` from your working v0.17 project, including its SDK path and Maps key. It is deliberately excluded from this ZIP.
4. Sync and Run. Version is **0.18.0**, versionCode **20**. Package ID and Android dependency/SDK versions are unchanged.

The provided original project had no complete command-line Gradle wrapper. Continue using your working Android Studio Gradle setup. Do not copy old source folders over v0.18.

## Choose the mode you want to test

**Offline prototype:** leave `RIDENOVA_API_BASE_URL` unset. Date/time selection and persisted upcoming rides work, but starting matching uses the explicit demo button. Offline mode has no background scheduling service. Cancellation is local and free while scheduled.

**Backend development:** use the v0.18 backend from this ZIP. From a terminal in the project folder:

```powershell
py -3 -m unittest discover -s backend -v
py -3 backend/server.py
```

Health: http://127.0.0.1:8080/health — should show `0.18.0`.

For a USB-connected Pixel, run `adb reverse tcp:8080 tcp:8080`, then add this to the project's `gradle.properties`, Sync and rebuild the debug app:

```properties
RIDENOVA_API_BASE_URL=http://127.0.0.1:8080
```

Use your Android SDK's `platform-tools/adb.exe` if `adb` is not on PATH. For the standard emulator use `http://10.0.2.2:8080`. Keep the Python terminal running; no hosted backend has been deployed. The default development area remains the Vancouver/Langley rectangle from v0.17. Real payments, OTP and driver dispatch are not connected.

If you already ran the v0.17 backend, stop it and back up its SQLite database before starting v0.18. To retain your development rides, point the new server at the **same** database explicitly:

```powershell
py -3 backend/server.py --database "G:\your-existing-folder\ridenova-dev.sqlite3"
```

Replace that example path with your actual database path. No SQL schema migration is needed; old records are retained. Otherwise the server creates a fresh database in its current working folder. After generating v0.18 statuses, use a v0.18 client with that database; v0.17 does not understand missed-schedule records.

## Scheduling test walkthrough

1. Select pickup/destination → Schedule → choose at least 16 minutes ahead to leave time for confirmation.
2. Get current fare, review the timestamp and price, then Confirm. The trip should appear under Upcoming.
3. Cancel one upcoming booking and verify that it moves to history with no fee.
4. Book another future pickup; restart the server and verify it remains in Upcoming.
5. At pickup time, leave the server running and observe SEARCHING within roughly 10 seconds (scheduler plus app polling). The app must not automatically show a real or fake assigned driver.
6. Optionally use the existing development admin simulator to advance the now-searching trip. See `START_HERE_v0_17.md` for token setup. Do not put the admin token in the Android app.

The CLI can also create a scheduled development booking:

```powershell
py -3 backend/dev_client.py book --schedule-minutes 60
```

It uses a separate passenger session from the phone. Do not change the computer clock to test missed pickups; the automated tests use an injected clock.

## Tested and still limited

29 distinct Python backend tests pass, covering existing booking/security checks plus schedule validation, conflicting pickups, capacity, schedule tampering, due-time activation, concurrent ticks, restart recovery, missed pickups, cancellation policy snapshots and the HTTP scheduling lifecycle. Nine Java date/time checks pass, including exact UTC conversion, booking limits and DST ambiguity handling.

**The Android app was not compiled or run in this workspace** because Android SDK/Gradle are unavailable. The pure Java helper was compiled and tested using the available JDK compiler module. Android UI and integration changes were inspected in source and still need Android Studio/Pixel testing.

Scheduling is a development reservation only, not a guaranteed vehicle booking. It uses a maximum of five upcoming rides and a 60-minute spacing rule. The server does not predict future traffic: it quotes using a route estimate calculated when you book. Prices remain fixed from the accepted quote in this prototype. Server-issued alternate routes, real authentication, payments, driver app, notifications, production hosting and operational/compliance work remain future tasks. Tax/minimum-fare configuration and the limited development service area are unchanged from v0.17; no new claim of regulatory approval is made.

The API details are in `backend/API_CONTRACT.md`. `START_HERE_v0_17.md` is retained for historical setup and simulator instructions; its statements that backend scheduling is disabled are superseded by this release.
