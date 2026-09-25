# RideNova Build 38 — Passenger matching-state hotfix (limited scope)

Based on the previously delivered, user-tested Build 36 project. This is **not** the full combined Build 38/39 staff-account/operations implementation. Those features have not been implemented and should not be treated as complete.

## Changes
- Passenger `RideNovaApp.kt`: matching now renders a temporary restore/loading view if a booking isn't yet in local state, instead of immediately showing `No active ride`.
- Reconciliation retains a recently created active booking for up to 30 seconds if a concurrent rides-list response does not yet contain it.
- Restore attempts lookup by the known ride ID and then the authenticated rides list, without sending another `POST /rides`. Retry 3 times; display recoverable error and Trips access after exhaustion.
- `updateTrip` inserts newly recovered rides rather than silently dropping them when missing locally.
- The existing backend ride-creation idempotency, authentication, driver app, Admin v2 portal, database schema and request rules are left unchanged.

## Installation
1. Back up your existing working Build 36 project and database.
2. Replace only the Passenger Android project, or just `Passenger/app/src/main/java/com/ridenova/passenger/ui/RideNovaApp.kt`, with the copy in this ZIP.
3. Keep your existing `gradle.properties`, `local.properties`, credentials and working backend settings. Do not replace or reset your database.
4. Gradle sync, compile Passenger and reinstall it. Run backend tests from the Passenger project root using `python -m unittest discover -s backend -p "test_*.py"`.

## On-device acceptance
- Sign in, confirm a Ride Now booking: see matching/loading immediately, never a brief `No active ride` flash.
- With driver online, confirm searching → offer → assigned → arrived → PIN → started → completed.
- Simulate temporary network interruption during initial matching; reconnect and verify the existing ride reappears without duplicate bookings.
- Relaunch app during an active ride, open Trips and resume it. Confirm scheduled rides still go to Upcoming Trips.
- Check Admin ride total before and after a test booking; only one new ride should exist.

## Verification limits
- Existing backend suite passed 115 tests on Linux; observed Python ResourceWarnings for some connections. Android Gradle compilation and physical-device reproduction have NOT been performed here.
- Full combined Build 38/39 staff accounts, backend-enforced RBAC, audit logging, server-side pagination, driver operations improvements are not part of this limited release. Existing Admin portal functionality is preserved unchanged.
