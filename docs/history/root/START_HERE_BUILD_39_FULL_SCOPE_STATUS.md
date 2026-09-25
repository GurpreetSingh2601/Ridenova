# RideNova Build 39 — Expanded operations release (scope and honest status)

**Base:** Build 39 Admin Role Clarity Increment, preserving its Build 38.2 hotfixes and staff-permission documentation.

## Implemented in this ZIP

- Admin Fleet workspace: opt-in server-side driver pagination (`paged=1`, page/limit max 100), indexed-field style searches by name, vehicle, plate or ID, approval-state filtering, next/previous page navigation, and actual server-reported totals. The previous unpaged API stays available to existing clients. The CSV button explicitly exports **only the visible page**, not all drivers.
- Admin Support workspace: opt-in server-side pagination and server-side status/search filters, next/previous navigation, totals, safe bounded inputs. The older unpaged endpoint retains its existing response for compatibility.
- Admin role-aware driver review: Compliance users see document review but not driver activation/suspension, driver credential reset or ride-eligibility mutation controls. Backend authorization is still authoritative; this frontend change is secondary UI clarity.
- Driver Android: more specific pending-approval and document-required messages on the home screen. Existing daily/weekly/all-time estimated earnings, trip history, and documents UX were already present and were preserved.
- Passenger Android: preserves Build 38 matching-state recovery and booking-busy guard unchanged to avoid risking a regression without real-device validation.
- New integration tests check fleet/support pagination, filtering, bad inputs, RBAC, and presence of Admin controls. Staff permission docs and development rules remain included.

## NOT implemented / NOT verified — please do not interpret this as a completed production release

- No new cross-device connection-recovery algorithm, GPS background redesign, ride idempotency protocol or payment idempotency changes. These are larger design/security changes that require device acceptance and backend consistency work.
- No driver push notifications, document expiry *notifications*, full data export, or new paid settlement workflow. Existing earnings are development estimates only.
- No comprehensive Windows, Android Gradle compilation, browser interaction, or Pixel device run was available in this environment. Backend unit/integration tests and inline JS syntax were checked; actual UX behavior must be tested.
- This remains a **development-only** application; do not expose Admin publicly or accept real money.

## Installation

1. STOP the development server. Back up your existing SQLite database and local configuration first.
2. Extract to a NEW folder (do not overwrite your only working copy).
3. Copy your existing database to its configured location, retain your Google Maps key and the same dev tokens/Owner credentials. Do not create a fresh Owner account on top of an existing database.
4. From `Passenger`, run `python -m unittest discover -s backend -p "test_*.py"` (Windows PowerShell) and verify no failures. Run the server with your existing database filename. Hard-refresh `/admin` with Ctrl+F5.
5. Test Owner and Compliance driver review separately; verify Compliance sees document review but no status, reset or ride-type buttons. Verify pagination by inserting multiple development drivers/cases; check filtered counts. Check Passenger booking and Driver offer flow on your phone.

## API additions (opt-in, backwards compatible)

`GET /v2/fleet/admin/drivers?paged=1&page=1&limit=25&status=PENDING&q=driver`
`GET /v1/admin/support-cases?paged=1&page=1&limit=25&status=OPEN&q=ride`

Both return the previous `drivers`/`cases` list plus `page`, `limit`, `total`, and `pages`. `limit` range: 1–100; page: 1–100000. Values must be URL encoded. Authentication and role permissions are required.

## Next work before Build 40

Passenger/Driver network recovery and idempotency, detailed QA of Driver onboarding and document reminders, Windows + physical-device acceptance, and production architecture/security planning. The title 'Expanded Build 39' does not mean these unfinished items are complete.
