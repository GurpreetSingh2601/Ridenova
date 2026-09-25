# RideNova Build 25 — Driver v0.7 navigation beta and UI refinement

Baseline: Build 24 Passenger v0.23, Driver v0.6.1, Admin v0.1, shared SQLite development backend. No database reset required.

## Changes
- Driver v0.7: Navigate opens a full-screen RideNova road-route experience, not an external app.
- Traffic-aware road polyline, distance, ETA and written maneuvers sourced from Google Routes API, refreshed every 30 seconds while open.
- GPS-follow camera, pickup/drop-off destination switches with trip state, route-failure message and Google Maps fallback.
- Explicit beta/safety messaging: this is *not* a complete turn-by-turn navigation SDK; no voice, lane guidance, background voice navigation or guaranteed automatic off-route rerouting. Use Google Maps fallback for actual driving until production navigation SDK is integrated and road tested.
- Updated earnings disclaimer to match Build 24 server ledger; no real payouts/charges.
- Existing Driver request sound, background GPS, Passenger, Admin and backend unchanged.

## Setup
1. Backup your Build 24 project and database. Use this ZIP as the new combined workspace.
2. Open the Driver project in Android Studio. Configure MAPS_API_KEY in local.properties or gradle.properties using the same Google Cloud project, enabling Maps SDK for Android **and Routes API** and confirming authorization/restrictions allow Routes API calls from the Android client.
3. Keep existing RIDENOVA_DEV_URL and RIDENOVA_DEV_TOKEN in local.properties; this release does not introduce new server endpoints.
4. Start the *same* Build 24 backend, connect Passenger and Driver, accept a ride, tap RideNova route to pickup, and confirm road polyline and instructions. After PIN/trip start, tap route to drop-off.
5. If routes fail, read the error panel; use Google Maps fallback. Do not attempt navigation by a straight line.

## Caveats
- Client-side Routes API key usage is development-only; proxy through secured backend before production.
- Route instructions shown are *not* location-matched; the list currently selects first step whose endpoint is >35 m away. This can be wrong on overlapping loops or backtracking. Do not use as the sole navigation source while driving.
- GPS must be tested on real devices; no Android Studio Gradle build or road test was possible in the delivery environment.
- Payment gateway, push notifications, Admin v0.2 and production driver navigation remain future milestones, not delivered in this version.
