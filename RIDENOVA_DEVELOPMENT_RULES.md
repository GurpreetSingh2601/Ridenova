# RideNova development rules

Updated for Build 42.1 UI/UX on 2026-10-03 UTC. Preserve this file in every later build.

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

- Run `python VERIFY_BUILD_42.py`.
- Require PostgreSQL concurrency, import and restore tests in `verification/postgres-integration.py`; SQLite and SQL syntax tests are not substitutes.
- Require matching API/worker revision and fresh heartbeat at `/ready` before inviting staging testers.
- Run all backend regression tests and add a targeted test for every regression.
- Syntax-check every Admin script and test role-gated navigation with Owner and restricted roles.
- Compile both Android projects when dependencies are available; test keyboard/insets, restart, offline/reconnect, background location and a full ride on real devices.
- Simulate simultaneous accepts, stale GPS, retries, duplicate actions, server restart and database reopen.
- Migrate a representative database copy and run SQLite `integrity_check` before production data is touched.
- Test the final release from a short Windows path and verify ZIP CRC/inventory.
- Record exactly what ran and what could not. Source preflight is not compilation; development tests are not production approval.

## Known current boundaries

- The CLI is development-only. Gunicorn/WSGI and invitation restrictions serve controlled staging. The user has a Build 42 Render setup; this Build 42.1 revision has not been deployed or provider-verified by this work.
- Build 42.1 passed 12 disposable PostgreSQL tests and both Android debug/staging compilations here. Device, hosted performance and real-provider acceptance remain distinct gates.
- Staging has conservative global request serialization/rate caps. Build 42 batches rate checks and logs phase timings; do not remove the request gate until atomic dispatch has independent guarantees.
- Managed backups, monitoring notifications and CI/CD account configuration require authorized setup and verification.
- OTP delivery, payouts and identity/document verification remain simulations. Stripe test payments are implemented behind test-key configuration; no live charge path is enabled.
- Passenger-selected Google routes are strictly validated and quote-bound, but production should request routes server-side.
- Physical-device acceptance remains required after installing the compiled sources with the correct staging URL and Maps key.
- BC launch, privacy, insurance, transportation, tax, worker-classification and accessibility obligations need qualified review.

## Product strategy through v1.0

- Build 41: authorized Render staging, PostgreSQL migration, secrets, backups/restore, monitoring, CI/CD and rollback, portable toward AWS. Never incur charges without owner authorization.
- Build 42: Stripe test sandbox, idempotent finance, refund/payout accounting design and capped boost-rule foundation.
- Build 43: trip sharing, emergency improvements and capped platform-funded boost zones. Avoid aggressive passenger surge pricing initially.
- Builds 44–47: BC compliance, scheduled rides/stops, communication/support, navigation/UX/performance.
- Builds 48–50: security/full regression, controlled BC beta and v1.0 candidate. Never claim public-launch approval without verification.

## Build 42 finance guardrails

- Only `sk_test_` credentials may configure Stripe; never store provider secret keys in Android, Git or logs. Checkout owns card data.
- A Stripe test card is distinct from a pre-existing development display reference. Test payments are explicit completed-ride actions; no public charge or payout can occur.
- Every monetary operation uses fixed idempotency keys, server-owned integer CAD cents, provider verification and unique ledger entries. Reconcile an ambiguous result before a different attempt.
- A boost is funded by the platform, capped by an atomic reservation, recorded once per ride and does not change the accepted passenger price.

## Build 42.1 UI maintenance rules

- Reuse each app's canonical launcher vector for brand marks; keep the existing Canadian tagline.
- Share typography, spacing, corners and semantic colours across screens. Do not equate styling with implementation of a service.
- Consume Scaffold insets before applying additional IME padding. Keep one scrolling form surface; avoid forced scrolling when a keyboard closes.
- Keep offer actions reachable independently of scrolling details. Respect large text and small/landscape screens.
- Keep Admin refreshes scoped to the visible workspace, with loading/error/freshness state. Abort/reject obsolete session requests and clear data on logout/401.
- Run the Admin browser regression after UI/request-lifecycle changes, in addition to server RBAC tests. Screenshots must label synthetic fixtures as such.
- Preserve Build 42 migration checksums. Build 42.1 adds no schema change; API `revision` remains the Git commit while `releaseRevision` identifies this release.
