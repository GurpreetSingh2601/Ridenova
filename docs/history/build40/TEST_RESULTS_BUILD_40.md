# Build 40 test results

Latest Windows verifier correction: all 137 backend tests passed in 26.378s in
the Linux packaging environment, followed by Admin and Android source preflight.
Full log: `verification/build40-windows-fix-tests.txt`. The test's oversized-body
rejection uses headers only to avoid the reported Windows upload/close race.
Windows rerun remains required; no Windows execution is claimed here.

Build 40 booking correction: the portable verifier was rerun against Passenger
0.32.1 source. Full output is in `verification/build40-booking-fix-tests.txt`.

## Implemented and automatically verified

| Check | Result |
|---|---|
| Full Python backend regression | PASS — 137 tests in 26.505 seconds (booking correction run) |
| Large-polyline HTTP booking and duplicate-safe replay | PASS — old 413 reproduced, compact confirmation succeeds |
| Selected-route → quote → booking regression | PASS |
| Invalid-route replacement disclosure | PASS |
| Explicit-decline suppression | PASS |
| Concurrent multi-driver claim | PASS |
| Stale GPS / eligibility exclusion | PASS |
| Duplicate Driver actions/events/earnings | PASS |
| Persistence and restart recovery | PASS |
| Staff authentication/RBAC/audit/session behavior | PASS |
| Admin required DOM/navigation and 5 inline script syntax checks | PASS |
| Android manifests, Kotlin delimiters and Build 40 source invariants | PASS preflight (not compilation) |
| Copy-only SQLite migration and integrity check | PASS |
| Shared server startup, `/health` 40.0 and `/admin` HTTP smoke | PASS |
| Original consolidated ZIP inventory/CRC | Previously passed; corrected archive is checked separately during packaging |

## Implemented but requires Windows / Android-device verification

- Passenger and Driver Gradle compilation. Attempted, but Gradle 9.6 could not be downloaded in this restricted environment.
- Google Maps/Routes key restrictions and real route rendering.
- Driver login/sign-up keyboard, scrolling and inset behavior on the affected device.
- Foreground/background GPS lifecycle across Android versions and OEM battery restrictions.
- Full Passenger → Radar/exclusive offer → Driver → completion → rating UI.
- Admin visual rendering in Chrome/Edge. JavaScript syntax/source structure passed; no full browser renderer was available.

## Not implemented / deferred

- Production hosting, PostgreSQL, monitoring, backup/restore automation, CI/CD and rollback (Build 41).
- Real payment/SMS/payout/identity verification.
- Production server-side Google Routes proxy; Build 40 validates and binds the Android-selected route.
- Public-launch, legal or regulatory approval.
