# Build 40 manual acceptance checklist

Use a copied database and keep the original untouched.

## Install and connect

- [ ] Extract to a short path such as `G:\RideNova\Build40`.
- [ ] Run `python VERIFY_BUILD_40.py` successfully.
- [ ] Compile Passenger and Driver with `gradlew.bat clean assembleDebug`.
- [ ] Start the shared backend and confirm `/health` reports build 40.
- [ ] Connect USB with `adb reverse tcp:8080 tcp:8080` or configure a trusted LAN URL.

## Passenger

- [ ] Select a Google road route; record distance/ETA, open confirmation and confirm the quote keeps it or clearly discloses a change.
- [ ] Confirm subtotal + GST = GST-inclusive total and the same total survives booking.
- [ ] Interrupt network just after requesting; reconnect and confirm only one ride exists.
- [ ] Navigate away, force-close/reopen and confirm the active ride recovers.
- [ ] Verify cancellation, assignment, arrived, started and completed status match Driver/Admin.
- [ ] Complete a ride and verify the bottom rating/safety prompt and history details.

## Driver / dispatch

- [ ] Test sign-up/sign-in with keyboard open, Next/Done, keyboard dismissal, rotation and a small screen; all fields/buttons remain reachable.
- [ ] Confirm a Driver cannot self-select Comfort/XL; Admin controls eligibility.
- [ ] Put two eligible nearby drivers online; accept the same Radar ride simultaneously and confirm one winner.
- [ ] Decline with one driver; confirm the unchanged ride is not repeatedly offered to that driver.
- [ ] Let Radar expire and confirm exclusive fallback; decline/expire it and verify reassignment.
- [ ] Make GPS stale and confirm exclusion; refresh GPS and confirm eligibility returns.
- [ ] Accept, disconnect, reconnect/reopen and confirm recovery without duplicate assignment.
- [ ] Repeat Arrive, Start and Complete; confirm one event and one earning.
- [ ] Open a completed trip and confirm exact pickup, route map and details.
- [ ] Verify location notification/service with screen off and after process recreation.

## Admin and data

- [ ] Sign in as Owner and verify sidebar/workspaces and Build 40 / Admin 0.7.0 labels.
- [ ] Test each role against `STAFF_PERMISSIONS_AND_TESTING.md`, including direct forbidden requests.
- [ ] Expire/disable a session and confirm 401 returns to sign-in without a broken page.
- [ ] Confirm ride pickup shows the exact address, not “Current location”.
- [ ] Verify paged rides, fleet, support, finance, staff and audit.
- [ ] Compare ride/passenger/driver/staff counts between original and migrated copy.
- [ ] Restart with the migrated copy and confirm accounts/history remain accessible.

