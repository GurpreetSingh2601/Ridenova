# Build 40 booking correction — Passenger 0.32.1

## Confirmed causes and changes

The quote request correctly accepts a large road polyline, but Passenger then
resent that same polyline inside the booking draft. Booking has a 32 KiB request
limit, so long routes were rejected with HTTP 413 before a ride was created.
Confirmation now sends only the existing quote token, selected tier and optional
payment-method ID. The server reads the preserved route and fare from the quote.
The defensive endpoint size limit and same-token retry behavior are retained.

The route-change reason was JSON null when no change occurred. Android's JSON
string conversion displayed it as literal `null`. Passenger now accepts a real
string only when `routeChanged` is true and otherwise displays no warning.

## Install

This ZIP contains the full consolidated Build 40 project. Extract into a new
short folder. Preserve your Maps key, API URL and local SDK configuration.
Rebuild/install the Passenger app (version 0.32.1-build40, versionCode 42) using
the same signing key, without uninstalling or clearing app data.

The booking correction requires the updated Passenger app. It works with the
previous consolidated Build 40 backend; no backend/database migration or Driver
reinstallation is required for these two fixes. Keep your existing database.

## Acceptance

Select the same long route to BC Place, open confirmation, verify that no `null`
warning appears and tap Confirm. Verify the ride enters matching, retains the
quoted route/fare and appears once in history/Admin. Complete normal Driver
acceptance and cancellation/trip checks using the existing Build 40 checklist.

## Verification scope

A new real-HTTP regression uses a 2,001-point route larger than 32 KiB. It
reproduces the old 413, verifies no ride was created by that rejected request,
then books successfully with a compact request and verifies route/fare retention
and duplicate-safe replay. Android source preflight checks the compact request
and null-safe parsing. Android compilation/device testing remains pending;
source preflight is not an APK build. Build 40 remains in acceptance testing.
