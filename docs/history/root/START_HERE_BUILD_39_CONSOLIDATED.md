# RideNova Build 39 — consolidated development release

This ZIP consolidates the previous Build 39 expanded operations and network-reliability changes and adds driver recovery improvements. It is a **development release**, not cleared for public launch.

## Implemented and preserved
- Admin staff roles, owner-managed staff accounts, role preview, role enforcement, audit, Fleet and Support server-side filtering/pagination.
- Passenger ride matching recovery and a single retry of read-only GET calls on connection I/O failure; never automatically replay booking POST.
- Driver read-only GET transport retries once on I/O failure, with disconnected connections in all outcomes. Driver POST mutations (accept, trip status, location, account actions) do **not** automatically replay after ambiguous failures.
- Foreground driver offer polling backs off to six seconds after three failures and fifteen seconds after six failures; success resets polling to two seconds. Existing GPS foreground location, authorization and offline handling preserved.
- Existing quote token booking de-duplication, demo payment and earnings behavior preserved. No payment processor has been connected.

## Verification in this environment
- Backend: 132 unittest tests passed.
- Driver Android Gradle compile: **not verified**; Gradle wrapper attempted to fetch gradle-9.6.0-bin.zip but this environment cannot resolve services.gradle.org. Build locally in Android Studio before use.
- Windows, browser, phones, background GPS, cellular handoff and cross-device acceptance: **not verified**.

## Remaining for later builds / public launch
- Processor-backed charges, refunds and payouts with provider idempotency keys. Demo payments cannot be used to take real money.
- Complete mutation idempotency across endpoints (not claimed in this release). Booking quote-token de-duplication is narrower.
- Dedicated production hosting, TLS, key management, migrations/backups, access/security audit, BC regulatory approvals and operational support.
- Phone tests of force-stop, battery restrictions, GPS permission revocation, background tracking, Wi-Fi/mobile handoff, duplicate taps and lost responses.

## Install and test
1. Stop the old server and back up the real SQLite database and local configuration. Do not overwrite the database with a fresh demo one.
2. Extract into a *new* directory. Transfer your existing DB/config according to your prior setup; do not run two backend servers simultaneously.
3. From Passenger: `python -m unittest discover -s backend -p "test_*.py"`.
4. Open Passenger and Driver in Android Studio and build them. Test a normal trip end-to-end and then disable/re-enable connectivity during driver offer polling and an active ride.
5. Verify roles separately in the Admin Portal using `STAFF_PERMISSIONS_AND_TESTING.md`. Do not expose this development server publicly or accept real payments.
