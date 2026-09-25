# RideNova Build 23 Major

## Versions
- Passenger Android: **v0.23**
- Driver Android: **v0.6**
- Shared development backend: **Build 23**

This build intentionally combines the planned Build 23 reliability work with part of the next earnings/persistence milestone. It continues to use **one shared RideNova backend** for Passenger and Driver.

## Major additions

### 1. Driver background GPS service
The Driver app now has an Android foreground location service. When the driver is online and location permission is granted, a persistent `RideNova Driver` notification keeps location publishing active while the Driver activity is backgrounded (for example, while Google Maps navigation is open).

The service publishes to the shared backend; it does not create a second Driver backend.

Important Android limitation: force-stopping the app, revoking location permission, or some OEM battery restrictions can stop the service. Reopening the Driver app restores server state and starts it again when permitted.

### 2. Server-owned online state recovery
Driver v0.6 now calls `GET /v1/driver/status` at startup. If the server still considers the driver online, the Driver app restores that online state instead of always resetting to offline.

If an active ride exists, the app restores the active ride and its stage from the shared server.

### 3. Background GPS updates the Passenger ride automatically
`POST /v1/driver/location` is now the authoritative driver presence feed. If the driver has an assigned ride, the backend also writes that GPS position into the active ride.

This means Passenger live driver location can continue updating even when the Driver activity is not visible.

### 4. Dynamic pickup ETA after assignment
While the driver is heading to pickup, each fresh GPS update recalculates the development pickup distance/ETA. The Passenger driver card therefore no longer has to keep the ETA that existed at the moment of acceptance.

If the driver is effectively at the pickup point (within ~150 m in the development estimator), the ETA is shown as 1 minute.

### 5. Live in-trip progress
After the PIN is verified and the trip starts, the backend publishes a `liveTrip` object containing:
- remaining distance
- estimated remaining minutes
- progress percentage
- last update time

Passenger v0.23 displays a new **Live trip progress** card while the ride is underway.

This is currently based on live GPS plus a development estimator. It is not yet a full traffic-aware server route recalculation.

### 6. Driver live next-stop information
Driver v0.6 displays live distance and approximate time to the next stop:
- pickup before the trip
- destination after the trip starts

The trip progress bar also advances from live device position during an active trip.

### 7. Driver trip/earnings history syncs from the server
The shared backend now exposes `GET /v1/driver/trips` for completed development rides. Driver v0.6 refreshes this history on startup and after trip completion, so the Earnings/Trips screens no longer depend only on the current in-memory trip completion event.

No real driver payout is created yet. These remain development earnings records.

## Backend verification
From the Passenger project root, with the development server stopped:

```bash
python -m unittest discover -s backend -p 'test_*.py'
```

Build 23 currently has **49 passing backend tests**.

## Driver setup
Keep the same values in Driver `local.properties` that you used in the previous working build:

```properties
MAPS_API_KEY=YOUR_KEY
RIDENOVA_DEV_URL=http://127.0.0.1:8080
RIDENOVA_DEV_TOKEN=YOUR_DRIVER_TOKEN
```

When testing on a physical Android phone through ADB USB/wireless debugging, keep using the same `adb reverse tcp:8080 tcp:8080` workflow if that is how your existing setup reaches the laptop backend.

The backend must use the same `RIDENOVA_DEV_DRIVER_TOKEN` value as the Driver app `RIDENOVA_DEV_TOKEN`.

## What to test first
1. Start the shared backend.
2. Start Passenger v0.23 and Driver v0.6.
3. Grant Driver location permission and notification permission when Android asks.
4. Go online in Driver.
5. Confirm the Driver banner says background GPS is active.
6. Request a Passenger ride and accept it in Driver.
7. Put Driver in the background or open Google Maps navigation.
8. Confirm the Passenger driver marker and pickup ETA continue refreshing.
9. Mark arrived, enter the Passenger PIN, and start the trip.
10. Confirm Passenger shows the new live trip progress card.
11. Complete the trip and verify it appears in Driver Trips/Earnings.
12. Close/reopen Driver while still online or during an active ride and confirm state is restored from the server.

## Still intentionally development-only
- payments are simulated; no card charge occurs
- driver authentication is still the development bearer token
- only the current development driver is dispatched
- server-side ETA/progress is not yet traffic-aware Google routing
- push notifications are not yet implemented
- production PostgreSQL/Redis infrastructure is not included yet
- driver verification/documents/payouts are not implemented yet

## Planned next milestone
The next major milestone can combine the pricing/earnings ledger, notifications, stronger route/ETA calculation, and the first Admin Web Portal foundation.
