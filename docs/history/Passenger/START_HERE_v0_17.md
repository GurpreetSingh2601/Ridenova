# RideNova v0.17 — Android + backend foundation

## Open and run the passenger app

1. Extract this ZIP to a **new folder**. Keep v0.16 as your backup.
2. Open the `RideNova_v0_17` folder in Android Studio (the folder containing `settings.gradle.kts`).
3. Add your existing Maps key to your own `local.properties`: `MAPS_API_KEY=your_key`. Do not share that file.
4. Sync Gradle, then Run on your Pixel. Version is **0.17.0**, versionCode **19**. Existing application ID is unchanged.

The app still runs locally with no backend configuration. Dependency and SDK versions are unchanged from the supplied v0.16 project. That archive did not contain gradlew scripts or gradle-wrapper.jar; this deliverable also does not claim to supply a complete command-line Gradle wrapper. Use your existing Android Studio Gradle setup.

## What changed

- Home displays **only the latest one recent destination**. Tap the main search bar for the full saved history, including remove/clear actions.
- Home measures the bottom card and passes that height to Google Maps as bottom padding, keeping its camera focus in the uncovered map area.
- Booking is two-step: **Get current fare → review → Confirm amount**. Expired quotes refresh and require another confirmation.
- Backend quote tokens are forwarded; repeated requests with the same token return the same ride.
- Server trips reload every five seconds. Local demo trips are kept separate from backend state. A live-trip header warns when polling fails.
- Backend mode never auto-assigns a fake driver. Demo state buttons are hidden. Cancellation goes to the server.
- The server persists trips and ordered trip events in SQLite, owns fare/fee calculations, enforces quote ownership and trip transitions, and prevents two active rides for one development session.
- Configurable Economy/Comfort/XL pricing, integer-cent GST breakdown, regulatory total floor, illustrative 30% commission allocation, two-minute grace and CAD $5 cancellation fee.

## Run the backend on your Windows computer

Install Python 3.11 or newer if needed. In a terminal in this project folder:

```powershell
py -3 -m unittest discover -s backend -v
py -3 backend/server.py
```

Health check: http://127.0.0.1:8080/health

No pip dependencies, database account, cloud service or payment account are required. The SQLite file is created in the terminal's working directory and survives restarts. Keep it private. No backend has been deployed for you.

## Connect your Pixel over USB (development/debug only)

1. Enable USB debugging and connect your Pixel. Accept its debugging prompt.
2. Run `adb reverse tcp:8080 tcp:8080` using Android Studio's Android SDK `platform-tools/adb` (or `adb.exe` on Windows).
3. Add this line to the project's `gradle.properties`:

```properties
RIDENOVA_API_BASE_URL=http://127.0.0.1:8080
```

4. Sync and rebuild the **debug** app. Leave the Python server running.
5. Use coordinates inside the Vancouver/Langley test area and choose **Ride Now**. Get a fare, review it, confirm, and inspect Trips.

For the standard Android emulator, use `http://10.0.2.2:8080` instead. Only these loopback/emulator domains allow HTTP in debug builds; release builds do not inherit that exception. Remove the property to return to the offline prototype. The server deliberately binds only to the computer's loopback address. Do not expose it publicly or enable blanket cleartext access.

## Simulate driver progress, explicitly

The backend does not dispatch real drivers. To test the state flow, set a long random `RIDENOVA_DEV_ADMIN_TOKEN` environment variable before starting the server and set the same value in a second terminal. Never embed it in the Android app or commit it.

Use the trip ID shown in the app's trip detail, or create a separate CLI test booking:

```powershell
py -3 backend/dev_client.py book
py -3 backend/dev_client.py advance --ride rn_REPLACE --status DRIVER_ASSIGNED
py -3 backend/dev_client.py advance --ride rn_REPLACE --status DRIVER_ARRIVED
py -3 backend/dev_client.py advance --ride rn_REPLACE --status TRIP_STARTED
py -3 backend/dev_client.py advance --ride rn_REPLACE --status COMPLETED
py -3 backend/dev_client.py events --ride rn_REPLACE
```

CLI passenger history is separate from phone history because each has its own development session. The admin simulator can advance either when given its actual ride ID. It is a testing tool, **not** a Driver app or Admin portal.

## Routing, pricing and limitations

Without `GOOGLE_ROUTES_API_KEY` in the server environment, routing is a clearly marked server-computed geographic approximation. Setting that variable enables server-side Google Routes; calls may incur charges. No live Google call was made during testing. Provider failure fails the quote rather than silently falling back. The backend currently recalculates its own Best route; it does not book the passenger's chosen alternate route. Review the updated distance/time in confirmation. Production needs server-issued route-choice tokens.

Backend scheduling is deliberately rejected: the old UI has human-readable labels, not unambiguous timestamps/time zones. Offline scheduling is unchanged. Multiple stops, real OTP authentication, driver identity/assignment, real payments, refunds, push notifications, payout accounting and complete safety/compliance workflows remain unfinished.

`backend/market.json` contains **development pricing**, not commercially approved rates. Its test-area rectangle is not a legal service-area boundary. Region 1's configured total floor is CAD $4.43, based on the PTB's announced August 18, 2026 update. The PTB page also displays an older embedded table, so verify the authoritative rule/license conditions before launch. GST is 5% and included in the floor. Cancellation is simulated; its tax treatment, dispatch-dependent charging policy and actual collection require further review. The illustrative commission allocation is not a settlement ledger or net driver earnings.

Official references checked September 12, 2026:

- https://www.ptboard.bc.ca/ride-hail-rates
- https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/gi-196/gst-hst-commercial-ride-sharing-services.html

## Verification and next work

17 automated backend tests passed, including HTTP quote/book/list/get/cancel, concurrent retries, tax/floor arithmetic, grace boundaries, ownership isolation, restart persistence and invalid transitions. Python syntax checked. Android changes received source inspection only: **this workspace has no Android SDK or Gradle executable, so an APK build and Pixel UI testing were not possible here**.

On the Pixel, check: Home with 0/1/many recent destinations; search-bar history; large font/small screen; location permissions; both fare-confirmation taps; server restart; airplane mode during a ride; retry after connection loss; cancellation; and the explicit admin simulator.

Before production: verified user authentication and role authorization; database migrations/PostgreSQL; robust web server/TLS and abuse controls; structured monitoring; pagination and retention; payment-provider idempotency and reconciliation; trusted route/service-area data; server-side scheduling; driver app with actual assignment/PIN verification; regulatory, insurance, privacy and security review. This v0.17 server intentionally refuses a non-development `RIDENOVA_ENVIRONMENT`.
