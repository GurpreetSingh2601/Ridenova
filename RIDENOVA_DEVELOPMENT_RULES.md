# RideNova development rules

Updated for Build 41 staging candidate on 2026-09-25. Preserve this file in every later build.

## Architecture

- `Passenger/` is the Passenger Android application (`com.ridenova.passenger`).
- `Driver/` is the Driver Android application (`com.ridenova.driver`).
- `Passenger/backend/` is the **one shared backend/API** used by Passenger, Driver and Admin.
- `Passenger/backend/admin/index.html` is the Admin portal served by that backend.
- Development persistence is SQLite; controlled staging uses PostgreSQL through versioned migrations. Never create a separate Driver backend.
- API/Admin and scheduler are two processes of the same shared backend. Both must run the same commit and database.

## Non-negotiable principles

1. Start from the newest accepted source; never copy older whole files over newer work.
2. Preserve compatible accounts, rides, events, staff roles, audit data and driver records. Migrations must be additive, backed up and tested on a copy.
3. Server state is authoritative for price, assignment, ride status, cancellation, eligibility, earnings and permissions. Apps recover state from the server.
4. Money uses integer CAD cents. The displayed total is GST-inclusive and `subtotalCents + gstCents == totalCents`. No real charge/payout is enabled until an accepted payment sandbox and idempotent ledger exist.
5. Booking and financial mutations require idempotency. A connection failure must never create a second ride, event, earning or charge.
6. Exactly one driver may claim a ride. Eligibility, online state and fresh GPS must be rechecked inside the atomic claim.
7. An explicit driver decline suppresses the unchanged offer for that driver. Expiry and explicit decline are distinct.
8. Admin authorization is enforced by the backend. Hiding controls is usability, not security. Never solve 401/403 errors by bypassing authentication or widening roles.
9. Never put API keys, passwords, bearer tokens or production secrets in source or release archives.
10. Keep source labels, Android versions, Admin labels, health metadata, filenames and release notes consistent with the real build.

## Required testing

- Run `python VERIFY_BUILD_41.py`.
- Require PostgreSQL concurrency, import and restore tests in `verification/postgres-integration.py`; SQLite and SQL syntax tests are not substitutes.
- Require matching API/worker revision and fresh heartbeat at `/ready` before inviting staging testers.
- Run all backend regression tests and add a targeted test for every regression.
- Syntax-check every Admin script and test role-gated navigation with Owner and restricted roles.
- Compile both Android projects when dependencies are available; test keyboard/insets, restart, offline/reconnect, background location and a full ride on real devices.
- Simulate simultaneous accepts, stale GPS, retries, duplicate actions, server restart and database reopen.
- Migrate a representative database copy and run SQLite `integrity_check` before production data is touched.
- Test the final release from a short Windows path and verify ZIP CRC/inventory.
- Record exactly what ran and what could not. Source preflight is not compilation; development tests are not production approval.

## Known Build 41 boundaries

- The CLI is development-only. Gunicorn/WSGI and invitation restrictions are implemented for controlled staging; deployment is not yet verified or authorized.
- PostgreSQL runtime validation and Build 41 Android compilation are blocked in this workspace. Do not label this candidate as the completed milestone.
- Staging has conservative global request serialization/rate caps. It is not load-tested for commercial dispatch.
- Managed backups, monitoring notifications and CI/CD account configuration require authorized setup and verification.
- OTP delivery, payments, payouts and identity/document verification are simulations.
- Passenger-selected Google routes are strictly validated and quote-bound, but production should request routes server-side.
- Android compilation and physical-device acceptance remain required for the new staging variants on a configured workstation or CI.
- BC launch, privacy, insurance, transportation, tax, worker-classification and accessibility obligations need qualified review.

## Product strategy through v1.0

- Build 41: authorized Render staging, PostgreSQL migration, secrets, backups/restore, monitoring, CI/CD and rollback, portable toward AWS. Never incur charges without owner authorization.
- Build 42: payment sandbox, idempotent finance, refunds/payout accounting and boost-rule foundation.
- Build 43: trip sharing, emergency improvements and capped platform-funded boost zones. Avoid aggressive passenger surge pricing initially.
- Builds 44–47: BC compliance, scheduled rides/stops, communication/support, navigation/UX/performance.
- Builds 48–50: security/full regression, controlled BC beta and v1.0 candidate. Never claim public-launch approval without verification.
