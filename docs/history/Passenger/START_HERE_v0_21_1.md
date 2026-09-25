# RideNova passenger v0.21.1 — Trip history and navigation hotfix

This is a passenger-app UI update on the combined v0.20/v0.21 foundation. The backend remains v0.21.0: no database migration or new admin commands are needed.

## Changes

- Recent trip cards show the local date and time of completion, cancellation or missed pickup. Active cards show request time; upcoming cards show booking time as well as scheduled pickup time.
- Trip details show the requested/booking date and time plus the final status date and time. This time reflects the last server status update; RideNova does not yet store an actual GPS-measured pickup/drop-off timestamp.
- Trip-detail maps show the saved booking geometry when present. Older server rides have only endpoints; while viewing details, the app asks Google Routes for a **current road-route preview**. If this cannot be obtained, a straight connection appears with an explicit approximation label. The road-route preview is not a record of the actual path traveled.
- Compact trip maps no longer request current-device location or show its blue GPS dot, so trip history stays centred on the trip.
- System Back from the Account and Trips tabs follows the same Home navigation/slide transition as tapping the Home tab.

Android version **0.21.1**, code **23**. The Python backend health endpoint still reports **0.21.0**; that is expected.

## Upgrade and test on your phone

1. Keep your earlier project and `ridenova-dev.sqlite3` database. Unzip this project and open its `RideNova_v0_21_Trip_History_UX_Hotfix` folder in Android Studio.
2. Copy `local.properties` from your working project into this folder for your private Maps key and SDK setting. Add the following line to the **project-level** `gradle.properties` (beside `settings.gradle.kts`):

```properties
RIDENOVA_API_BASE_URL=http://127.0.0.1:8080
```

3. Keep the existing v0.21 backend running against the **same** SQLite file used for your previous account/trips. If the server lives in a different project folder, pass the full database path with `--database` as described in `START_HERE_v0_21.md`.
4. When using wireless debugging, make sure the phone is connected and run `adb reverse tcp:8080 tcp:8080` (using the full path to adb if needed).
5. Sync Gradle, rebuild and Run the **same app** on your phone. Do not uninstall or clear app data to apply this hotfix.
6. Visit Trips → Recent and open a completed trip. Verify date/time and map. Try Android's Back button/gesture from Account and from Trips; compare it with tapping Home.

Road-route previews require the working Google Maps/Routes key and an internet connection on the phone. Each old trip-detail view may request a fresh route; if routing is unavailable, the labelled approximation remains. No payment or driver-dispatch behaviour changes in this hotfix.
