# Build 41 release notes — staging candidate

This milestone moves the accepted local RideNova architecture toward hosted staging.
The complete Passenger, Driver, Admin and single shared backend source is included.
Local SQLite workflows remain available; the original database is not replaced.

Implemented changes:

- PostgreSQL adapter and versioned baseline/operations migrations; 64-bit timestamps,
  exact integer-cent money, binary document storage and preserved column ordering.
- Database-backed locking across HTTP workers and scheduler; existing claim/retry/
  decline rules retained. Controlled staging is intentionally serialized.
- Restricted staging login, disabled simulator/token-only registration endpoints,
  individual staff authorization, HTTPS/origin validation and bounded request rates.
- Health/readiness with schema, Owner, heartbeat and commit checks; privacy-conscious
  structured application logging; separate scheduler process.
- Safe SQLite import, identity-sequence reset, environment session invalidation,
  checksum backup and empty-target restore verification tools.
- Render configuration, portable container, CI regression/Android jobs and manual
  deployment workflow with revision checks and documented rollback.
- Separate HTTPS-only Android staging apps; fixed Driver non-debug backend/location
  wiring. Existing icons, branding, trip UX and data flows are preserved.
- Admin version/environment labels, Compliance data boundary, Node preflight errors,
  Windows Gradle error handling and accurate release documentation.

No actual deployment, payment integration, SMS verification, public beta, cloud
restore drill or production approval is claimed. See `TEST_RESULTS_BUILD_41.md` and
`KNOWN_ISSUES_BUILD_41.md` before using this candidate outside local development.
