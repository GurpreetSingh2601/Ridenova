# RideNova Passenger 0.34.0 — Build 42

This Android app uses the one shared RideNova backend in `backend/` for authentication, account data, quotes, booking, ride recovery, live status, history, ratings and support.

Build 41 binds the selected Google road route to the server quote and booking, uses a server-authoritative GST-inclusive price, safely replays an ambiguous create request with the same quote token and recovers active ride state from the backend.

Setup and database instructions are in the repository-root `START_HERE_BUILD_41.md`. This remains a development build: no real SMS, card charge, payout or production hosting is connected.


Build 42 adds hosted Stripe test card setup and a completed-trip test authorization action. Production payment remains disabled.
