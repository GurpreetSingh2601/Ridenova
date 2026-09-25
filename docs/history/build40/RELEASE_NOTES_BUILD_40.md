# RideNova Build 40 release notes

Passenger 0.32.1 booking correction: Confirm sends only quote token, tier and
payment reference to avoid HTTP 413 on long routes. Optional route warnings no
longer display literal `null`. See `BOOKING_FIX_BUILD_40.md` for installation.

## Passenger

- The selected Google road route is sent with its polyline, validated server-side, bound to the quote token and preserved into the ride.
- Confirmation fetches the authoritative quote immediately instead of displaying a local fare as final before another calculation.
- Genuine route replacement is explicit through `routeChanged` and `routeChangeReason`.
- Fares remain server-calculated; integer-cent breakdown labels the total as GST-inclusive.
- An ambiguous booking network failure replays the same quote token once, returning the existing ride instead of creating another.
- Active rides continue to recover from backend state after navigation/reopening.
- `RideNovaHttpClient.kt` connection construction was repaired and structurally checked.

## Admin

- Restored role-aware navigation for Dashboard, Live operations, Rides, Drivers / Fleet, Finance, Support, Trip feedback, Staff & Access and Audit Logs.
- Removed null DOM assumptions behind the `hidden` error and exposed the ride paginator consistently.
- Expired/invalid sessions clear local session state and return to sign-in; authentication is not bypassed.
- Current labels are Build 40 / Admin 0.7.0.
- Added dependency-free Admin DOM/JavaScript preflight checks.

## Driver and dispatch

- Preserved atomic first-winner assignment, eligibility checks, fresh-GPS requirements, Radar fallback and active-trip recovery.
- Explicit declines suppress the unchanged searching ride for that driver; cleanup occurs after it leaves search.
- Repeated arrive/start/complete remains idempotent, preventing duplicate events and earnings.
- Foreground location service declares its location type at startup and is restartable after process reclamation.
- Driver version is `0.17.0-build40`; visible old Build 35 labels were removed.

## Operations

- Added copy-only database migration/validation.
- Added route, route-rejection disclosure and decline regression tests.
- Added one portable verifier and removed stale Admin test references.
- Consolidated current documentation and preserved historical notes under `docs/history`.
