# RideNova change log

## Build 42 sandbox staging candidate — 2026-09-28

- Add Stripe test-only hosted card setup, explicit completed-trip authorization, Owner capture/refund and reconciliation using stable provider idempotency keys.
- Add additive finance, sandbox and boost tables, role-gated Admin Finance controls and capped platform-funded bonus awards.
- Batch API rate-limit database checks and log handler, lock and rate-check timings for investigating the reported staging slowness.
- Preserve existing data and simulated cards; update both Android version labels and the Passenger payment flow.
- Status: candidate pending disposable PostgreSQL CI, Android compilation, real Stripe test provider, Render staging and phone verification.

## Build 41 staging candidate — 2026-09-25

- Preserve accepted Build 40.1 functionality; add shared PostgreSQL compatibility,
  immutable schema migrations and a fail-safe SQLite importer with content checks.
- Add Gunicorn WSGI transport, cross-worker request/transaction locks, invitation-only
  staging access, rate limits, HTTPS/origin guards and same-commit worker readiness.
- Add backup/restore tools, Render Blueprint, container packaging, CI and a protected
  manual deployment workflow. No cloud deployment or charges initiated.
- Add isolated Passenger/Driver staging variants and remove Driver debug-only gates
  that prevented real login, trips and location updates in a non-debug variant.
- Correct Compliance overview ride-data exposure and avoid forbidden ride fetches
  from that role's dashboard. Existing role grants are not broadened.
- Correct PostgreSQL rating serialization, reserved SQL identifier, Gunicorn logging
  startup, and Windows Gradle wrapper error fallthrough. Add targeted checks.
- Status: candidate, pending actual PostgreSQL execution, Android compilation,
  authorized cloud setup/restore/monitoring and separate-network device acceptance.

## Build 40 Windows verifier correction

- Make the oversized-request negative test check header-based HTTP rejection
  without a concurrent body-upload/connection-close race on Windows.
- Keep strict 413/BODY_TOO_LARGE assertions and the full large-route positive test.
- Runtime application code and database schema are unchanged.

## Build 40 booking correction — Passenger 0.32.1

- Send quote token, tier and payment reference when confirming; do not resend
  stored route geometry and exceed the booking body limit.
- Parse optional route-change reasons without displaying JSON null as text.
- Add a large-route real-HTTP test covering 413 reproduction, successful compact
  booking, exact quote preservation and idempotent replay.
- No database schema changes. Build 40 acceptance remains pending.

## Build 40 — 2026-09-22

- Consolidated Passenger 0.32.0, Driver 0.17.0, shared API 40.0 and Admin 0.7.0.
- Fixed selected-route → quote → booking consistency and route-change disclosure.
- Fixed Passenger HTTP construction and safe idempotent booking replay.
- Restored Admin navigation, staff sessions, Audit Logs and paginator visibility.
- Strengthened unchanged-offer decline suppression while preserving atomic dispatch/expiry fallback.
- Updated Driver foreground location service startup.
- Added copy-only database migration, targeted tests and portable verification.
- Replaced stale release metadata and consolidated current documentation.

Historical notes are preserved under `docs/history/`; current behavior is defined by Build 40 source and documentation.
