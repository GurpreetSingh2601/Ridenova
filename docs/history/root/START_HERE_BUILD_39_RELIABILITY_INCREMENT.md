# Build 39 reliability increment — verified scope

This patch extends Expanded Build 39. It is **not** the full outstanding reliability roadmap.

## Changes
- Passenger network transport: one delayed retry of read-only GET on connection failures only; no retry for HTTP errors.
- Passenger transport: HttpURLConnection is disconnected in a finally block, including failures while writing/reading/parsing.
- Existing quote-token booking idempotency is preserved; POST and PATCH are **never** automatically replayed. Existing ride-recovery UX stays intact.

## Not yet implemented or verified
- Driver Android connection recovery and GPS background redesign; end-to-end cross-device reliability and real-device tests.
- Explicit idempotency keys for all mutation endpoints, payment processor charge/refund/payout idempotency; the existing payments are development-only.
- Driver document expiry push notifications and full onboarding/device QA; full export and production staging/security.
- Android Gradle compilation and Windows/Pixel acceptance (must run on developer equipment).

## Installation and tests
Stop the server and back up the original database. Extract to a separate folder and migrate your existing DB/config as before. From Passenger run `python -m unittest discover -s backend -p "test_*.py"`; build Passenger in Android Studio and test offline/reconnect while viewing an active ride. Verify booking after an ambiguous network timeout by opening Trips **before booking again**. Do not use real payments or expose Admin publicly.
