# RideNova v0.21.3 — ride-state and driver-map foundation

This build continues v0.21.2. A finished ride on Home now reads **Past ride · Completed** and opens trip details; an in-progress ride reads **Active ride** and opens its live status screen. Payment methods opened from booking have **Continue to booking** below the cards. Cards retain their order and selection.

## Update on your phone without losing data

1. Extract this ZIP and open `RideNova_v0_21_3_Ride_Map_Foundation` in Android Studio. Keep your existing phone app installed; do not clear app data.
2. Copy your private `local.properties` and your working `RIDENOVA_API_BASE_URL=http://127.0.0.1:8080` Gradle setting into the new project if applicable.
3. Stop the old server with Ctrl+C. Start this version's `backend/server.py` and point it to the **same SQLite file** you previously used; for example in PowerShell:

   ```powershell
   python backend/server.py --database "G:\path\to\your\existing\ridenova-dev.sqlite3"
   ```

   If using the admin simulator, set `RIDENOVA_DEV_ADMIN_TOKEN` again in the same terminal. Keep that terminal open. `http://127.0.0.1:8080/health` should say `0.21.3`.
4. If wireless debugging reconnected, repeat your working `adb reverse tcp:8080 tcp:8080` command for the phone. Sync Gradle, build and run version 0.21.3 (`versionCode 25`) without uninstalling.

## What the map does today

The app looks up the planned driving route when the ride has coordinates and a Google Routes key. The development admin can report a **test position**, shown as an orange marker. When a test position is reported during `DRIVER_ASSIGNED`, the app requests a green driving route from that point toward pickup. `DRIVER_ARRIVED` puts a marker at pickup as **reported arrival**, not GPS confirmation. During `TRIP_STARTED`, fresh reported positions appear on the planned route and the approximate travelled section is green. Positions more than 30 seconds old disappear and the UI says they are stale. No GPS location is fabricated. Real driver authentication, mobile GPS publishing and automatic live tracking still belong to the driver/dispatch phase.

Optional position test after advancing a trip to `DRIVER_ASSIGNED` (replace the trip ID and coordinates with your own test values):

```powershell
$rideId = "rn_REPLACE_WITH_YOUR_TRIP_ID"
$headers = @{ Authorization = "Bearer $env:RIDENOVA_DEV_ADMIN_TOKEN" }
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/v1/admin/rides/$rideId/driver-position" -Headers $headers -ContentType "application/json" -Body '{"latitude":49.18,"longitude":-122.85}'
```

This admin endpoint runs on the laptop's loopback-only development server and requires your admin token. It accepts valid coordinates only while the ride is assigned, arrived or started. The rider app reads positions from its normal 5-second ride sync. Send an updated test position to move the marker. Do not send private driver GPS data to this test endpoint. Real production driver locations will require an authenticated driver API and appropriate retention/privacy controls.

If Routes API is unavailable, the map keeps the endpoints and explains that route geometry or location is unavailable; it will not draw a fake road route. Previous setup notes are in `START_HERE_v0_21_2.md`.
