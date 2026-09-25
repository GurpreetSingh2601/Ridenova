# RideNova Build 28 — multi-driver foundation (development preview)

## What is implemented
- All Build 27 Passenger v0.24, Driver v0.9, Admin v0.1 and API code retained without overwriting their Android source.
- New isolated, persistent `fleet_*` SQLite tables created on server startup; existing tables/data are not dropped.
- Separate per-driver development credentials and registered driver profiles.
- Admin-gated status decisions (PENDING / APPROVED / SUSPENDED), with audit events.
- GPS freshness, online approval gating, 20-second offer leases, nearest eligible category matching and transactional acceptance.
- Read-only document requirement checklist. **No document upload, validation or approval is implemented.**

## NOT yet implemented / important limitations
- The existing Driver Android client still uses legacy `/v1/driver` and the original development token. The new `/v2/fleet` API is not wired into the Android UI; this is a backend integration foundation, not the promised end-to-end multiple-phone onboarding release.
- Existing Passenger availability and legacy driver dispatch remain single-development-driver. Multi-driver fleet offers are independently testable via API, but production dispatch selection and fleet trip completion/history are not yet unified.
- No secure real-world login, verified phone, driver identity check, file uploads, document approval, tax handling, live push notifications, payouts, or production operations portal.
- Do NOT place a real driver's documents, tax IDs or real credentials into this development server.
- Development-only HTTP server: keep loopback access. Never publish its registration/admin routes to the internet.

## New test API (use test data only)
- `POST /v2/fleet/register`: JSON `name`, `vehicle`, `plate`, `category` (ECONOMY, COMFORT, XL). Returns one development token, store privately.
- Admin token: `GET /v2/fleet/admin/drivers`; `POST /v2/fleet/admin/drivers/{driverId}/status` with `{"status":"APPROVED"}`.
- Driver bearer token: `POST /v2/fleet/driver/presence` with `{"online":true,"latitude":49.2,"longitude":-122.9}`; `GET /v2/fleet/driver/offer`; `POST /v2/fleet/driver/rides/accept` with `{"rideId":"..."}`; `GET /v2/fleet/driver/documents`.

## Setup
Back up your database. Run the existing shared server from its original project directory, with existing environment variables. Never overwrite a customized MySQL backend with this SQLite sample. Run `python -m unittest discover -s backend -p "test_*.py"` from Passenger project root. The fleet test suite is included.

## Verification record
The existing 50 backend tests plus 2 new fleet unit tests passed in this environment. Android Gradle compilation, Windows testing, API-level integration on real devices and migration against your customized database were NOT performed. Legacy `/v1/driver` and new `/v2/fleet` dispatch must not be used simultaneously with live passengers because cross-system offer exclusion is not fully integrated.
