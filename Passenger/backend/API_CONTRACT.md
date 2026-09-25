# RideNova Build 41 API — local and controlled staging contract

Passenger Android, Driver Android and Admin use this single shared Python API.
SQLite is retained for development; staging uses PostgreSQL and the WSGI transport.
Build 41 reports `version: 41.0` and `build: 41` from
`GET /health`.

Staging `/health` includes environment and deployed revision. `/ready` returns
200 only when migration checksums, active Owner, fresh scheduler and matching
revision checks pass; otherwise it returns 503 without database details.

Staging requires HTTPS and the configured Host/Origin. Staff authorization is
mandatory; shared development tokens never grant access. The passenger OTP
request returns an invitation challenge without `developmentCode`; the invited
tester uses a privately assigned test code. No SMS or phone verification occurs.
Unknown passenger/driver invitations are rejected. Driver accounts are provisioned
privately; token-only registration, public driver signup, development recovery,
legacy `/v1/driver` routes and Admin simulated trip transitions are disabled.
The normal `/v2/fleet/driver` account/trip APIs remain available to invited drivers.

See root deployment documentation for body limits, rate caps, security boundaries
and actual verification status. Staging mutations retain the existing idempotency
contract; clients must recover uncertain results rather than create another ride.

## Build 41 route, booking and dispatch reliability

`POST /v1/passenger/quotes` accepts the selected Google road-route snapshot in
`route`, including its bounded polyline. The server validates its endpoints,
geometry, distance and duration before using it. When valid, that same route is
bound to the quote token and ride. When rejected, the response sets
`routeChanged: true` and gives `routeChangeReason`; clients must disclose the
change before confirmation. The server always calculates the fare and its
inclusive GST breakdown. Client-supplied fare values never control a booking.

`POST /v1/passenger/rides` remains idempotent by quote token. Replaying the same
token and tier returns the existing ride, including after a lost response;
reusing it with a different tier returns HTTP 409.

Trip Radar and exclusive acceptance use serialized transactions (SQLite locally,
PostgreSQL advisory locks in staging) designed so exactly one
driver can own a ride. A driver's explicit decline remains suppressed for that
unchanged SEARCHING ride; suppression is cleaned up when the ride changes or
becomes terminal. Expired offers can still be dispatched according to the normal
fallback policy. Driver arrive/start/complete actions are idempotent and do not
duplicate events or earnings.

## Build 34 trust and support additions

- `GET /v1/passenger/rides/{rideId}/experience`
- `POST /v1/passenger/rides/{rideId}/rating`
- `GET|POST /v1/passenger/support-cases`
- `GET /v2/fleet/driver/rides/{rideId}/experience`
- `POST /v2/fleet/driver/rides/{rideId}/rating`
- `GET|POST /v2/fleet/driver/support-cases`
- `GET /v1/admin/feedback`
- `GET /v1/admin/support-cases`
- `POST /v1/admin/support-cases/{caseId}/status`

Ratings accept `stars` (1–5), up to five allowlisted `tags`, and an optional `comment` of up to 500 characters. Support cases accept an optional authorized `rideId`, an allowlisted `category`, and a 10–1000 character `description`.

## v0.21 account data and payment foundation

All endpoints below require the passenger bearer token. Saved places accept only `home` or `work`. Recent destinations are deduplicated by Places ID/address and capped at eight. Payment methods contain development display references only; raw card numbers and CVVs are never accepted.

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/passenger/account-data` | Return `{savedPlaces:{home?,work?},recentDestinations:[]}` |
| POST | `/v1/passenger/saved-places` | `{action:save,slot,place}` or `{action:remove,slot}` |
| POST | `/v1/passenger/recent-destinations` | `{action:add\|remove,place}` or `{action:clear}` |
| GET | `/v1/passenger/payment-methods` | Return account-owned references; seed a development Visa ending in 4242 when needed |
| POST | `/v1/passenger/payment-methods` | Add `{brand,last4,expiryMonth,expiryYear}` display reference; maximum five |
| POST | `/v1/passenger/payment-methods/{id}/default` | Make an owned method default |
| POST | `/v1/passenger/payment-methods/{id}/remove` | Remove an owned method; the final method cannot be removed |

Ride creation additionally accepts `paymentMethodId`; the server verifies ownership and snapshots `{methodId,type,brand,last4,status,amountCents,developmentOnly}` into the ride. Missing IDs use the passenger default for backward compatibility. Status values are `NOT_CHARGED`, `CAPTURED_DEMO` and `VOIDED`; no money moves.

## v0.19 authentication additions (supersede anonymous-session authentication below)

The v0.19 passenger API requires `Authorization: Bearer <access token>`. `X-RideNova-Session` no longer authorizes passenger endpoints. During `verify-otp` only, a valid legacy session header is hashed and any matching pre-v0.19 rides/quotes are reassigned to the authenticated passenger account. This migration is idempotent; logout does not delete server data.

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/auth/request-otp` | `{phone}` → challenge, five-minute expiry, 60-second resend delay and development code |
| POST | `/v1/auth/verify-otp` | `{challengeId,code}` → passenger, access token and refresh token |
| POST | `/v1/auth/refresh` | `{refreshToken}` → rotated access/refresh pair; old refresh is revoked |
| POST | `/v1/auth/logout` | `{refreshToken}` plus current bearer revokes the session; the app clears local authentication even if offline |
| GET | `/v1/passenger/me` | Returns authenticated passenger profile |
| PATCH | `/v1/passenger/me` | Replaces validated first name, last name and optional email; phone is immutable |

Canadian `+1` input is normalized to E.164-like `+1` plus ten NANP digits. This development validator does not prove that every accepted number is assigned, mobile or currently Canadian. The code is deliberately returned to the local Android app and expires after five minutes; five wrong attempts lock the challenge. Consequently this is an account/session architecture test, **not real phone verification**. Production requires an SMS provider, server-held OTP secret/pepper, anti-abuse controls and verified consent/delivery handling.

Access tokens expire after 15 minutes. Refresh tokens expire after 30 days. Both are random opaque values and only SHA-256 hashes are stored in SQLite. Android encrypts the plaintext pair using AES-GCM with an app-private Android Keystore key and performs at most one serialized refresh/retry after a 401. A temporary network failure retains the refresh token; a rejected refresh clears local authentication. The development server has no global session-management UI, device list, phone-change flow or account deletion yet.

The backend database migration adds `passengers`, `otp_challenges` and `auth_sessions`; existing v0.18 ride tables and data remain. Back up the SQLite file before upgrading. Use the v0.19 Android app with the v0.19 backend: v0.18 clients receive 401 from passenger endpoints.

## v0.18 scheduling additions (supersede the Ride Now-only descriptions below)

`POST /v1/passenger/quotes` accepts either `{scheduled:false}` with no scheduled timestamp, or `{scheduled:true, scheduledAtEpochMs:<integer UTC milliseconds>, scheduleTimeZone:<display zone ID>}` alongside pickup/destination. Initial quote validation requires 15 minutes–30 days lead time. The timestamp is authoritative; the zone ID is bounded display metadata and is never used by the server to shift the instant. Android resolves unambiguous local times before sending the timestamp and displays returned timestamps in the device's current zone with a numeric UTC offset. Server-generated labels use UTC.

The quote binds the schedule, fare, grace period and fee. Create uses that stored snapshot and ignores the submitted draft. During the 120-second quote lifetime it permits the already-quoted pickup as long as it is not in the past. A consumed quote remains idempotent, including after its expiry. New scheduled requests create `SCHEDULED` trips; immediate bookings create `SEARCHING` trips.

An owner can have up to five upcoming rides, with at least 60 minutes between scheduled pickup times, plus one live ride. This is a simple development rule, not a route-duration conflict planner. Future reservations do not block immediate bookings. The five-second background scheduler activates a due reservation only if the owner has no live trip; delayed reservations wait up to 15 minutes, then become `SCHEDULE_EXPIRED` with no cancellation fee. Expiry is strictly after the 15-minute boundary. Scheduler ticks are atomic and restart-safe. No real driver is dispatched.

`SCHEDULED` → `SEARCHING` is scheduler-owned. Activation starts a fresh grace period using the quoted policy. `SCHEDULED` → `CANCELLED_BY_RIDER` is free, even after the original booking grace; later cancellations follow the ride's normal policy. `SCHEDULE_EXPIRED` is terminal and cannot be assigned or cancelled. New event types: `RIDE_SCHEDULED`, `SCHEDULE_ACTIVATED`, `SCHEDULE_EXPIRED`.

The v0.18 scheduling data format remains supported by v0.19. Older clients do not know every current status or the new authentication contract. Keep a database backup before upgrading. The scheduler starts only from the documented `python backend/server.py` entry point; code embedding `Service` must invoke `activate_due()` itself.

Fare breakdown data is displayed in Android confirmation, live ride and trip details. It is still development pricing, and scheduled duration estimates are calculated at booking time, not predicted traffic at the future pickup. There are no production guarantees, deposits, reservations with real drivers, notifications or actual charges.

All bodies/responses are JSON. Money in `breakdown` uses integer CAD cents; `fareCad` and `cancellationFeeCad` are decimal compatibility fields for Android. Epoch timestamps are integer milliseconds. Non-2xx responses contain `code` and human-readable `message`; the HTTP response also has `X-Request-ID`. Bodies are limited to 32 KiB.

Historical v0.18 clients used `X-RideNova-Session` as passenger authority. v0.19 accepts this identifier only on OTP verification for one-time legacy ownership migration; all passenger data access requires a bearer token.

| Method | Path | Request / result |
|---|---|---|
| GET | `/health` | Public development health/version |
| POST | `/v1/passenger/quotes` | `{pickup, destination, scheduled:false}` → `{quoteToken, expiresAtEpochMs, currency, options, route, cancellationPolicy, pricingVersion, developmentOnly}` |
| POST | `/v1/passenger/rides` | `{quoteToken, rideOption:{tier}}` → RideTrip; other supplied fares/draft fields do not control the stored ride |
| GET | `/v1/passenger/rides` | `{rides:[RideTrip]}` owned by this session, newest first |
| GET | `/v1/passenger/rides/{id}` | Owned RideTrip |
| POST | `/v1/passenger/rides/{id}/cancel` | `{}` → updated RideTrip; repeated cancellation is a no-op |
| POST | `/v1/admin/rides/{id}/transition` | `{status}` → RideTrip; development simulator only |
| POST | `/v1/admin/rides/{id}/driver-position` | `{latitude,longitude}` → RideTrip with `driverPosition`; test-only, active assigned rides only |
| GET | `/v1/admin/rides/{id}/events` | Ordered `{events:[{sequence,atEpochMs,type,data}]}` |

Admin endpoints additionally require `Authorization: Bearer <RIDENOVA_DEV_ADMIN_TOKEN>`. They are disabled when the environment variable is absent. Passenger session values cannot grant admin access.

Place = `{name, address, latitude, longitude}`. Coordinates must be finite and inside the development rectangle. Tier = `ECONOMY | COMFORT | XL`. Route = `{distanceKm, durationMinutes, routeType:"BEST", isApproximate}`.

RideTrip follows the Kotlin model: `id`, `draft` (pickup/destination/selectedTier/routeEstimate/scheduled/scheduleLabel), `option` (tier/title/description/etaMinutes/fareCad/seats/breakdown), `status`, requested/updated/grace timestamps, optional `driver`/`pin`, cancellation fee. Optional `driverPosition` has `latitude`, `longitude` and server-assigned `recordedAtEpochMs`; it is unverified development-admin simulator data, not live driver GPS. Additional server fields include pricing version, development marker and a snapshot of the after-grace cancellation fee. Driver ETA is unknown before assignment (`etaMinutes:0`).

Allowed simulator sequence: SEARCHING → DRIVER_ASSIGNED → DRIVER_ARRIVED → TRIP_STARTED → COMPLETED. Rider cancellation is permitted only in the first three states. No event is emitted for idempotent repeats. SQLite transactions make trip writes and event writes atomic. Events are ordered records, not tamper-proof audit storage.

Quote tokens bind owner, route, prices and expiry. A token can create one trip only. Replaying the same tier returns that trip even after expiry. Reusing it for a different tier returns 409. Different tokens cannot create simultaneous active trips for the same owner. Quotes expire after 120 seconds; cancellation grace is independently measured from trip creation. No charges are actually collected.

Future Passenger/Driver/Admin applications should share these status names and currency/timestamp conventions. **No `/v1/driver` endpoints are implemented**: driver authentication, assignment ownership and verified trip-start PIN must precede those endpoints. Never give the future Driver app the development admin token.

## Build 23 additions

### `GET /v1/driver/status`
Driver-authenticated. Returns server-owned online state, development driver profile, last known location metadata, and active ride id/status when present.

### `GET /v1/driver/trips`
Driver-authenticated. Returns completed rides assigned to the development driver for Trips/Earnings synchronization.

### `POST /v1/driver/location`
Build 23 extends this endpoint: driver presence also updates the assigned ride's `driverPosition`. During `DRIVER_ASSIGNED`, it refreshes pickup ETA; during `TRIP_STARTED`, it adds `liveTrip` remaining-distance/ETA/progress fields for Passenger polling.
