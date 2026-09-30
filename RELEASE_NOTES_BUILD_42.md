# Build 42 release notes — staging candidate

Passenger `0.34.0-build42` (44), Driver `0.19.0-build42` (40), shared API `42.0`, Admin `0.9.0`.

- Bundles Build 41 PostgreSQL payment-method order fix.
- Batches staging request rate checks in one PostgreSQL transaction and logs `rateMs`, `lockWaitMs`, `handlerMs` to isolate the 650–2200 ms API latency shown in Owner's Render screenshot. The request gate remains conservative for correctness. No speed improvement is claimed before hosted measurement.
- Adds Stripe **test-mode-only** hosted card setup, completed-trip manual authorization, Owner capture/refund, test finance ledger and provider reconciliation. Production mode and payouts remain disabled.
- Adds owner-configured, disabled-by-default capped platform-funded boost circles. Completion awards once within budget, without changing accepted passenger fares.
- Adds an Admin Finance workspace and Passenger staging test-card flow; preserves staff role restrictions and existing data.
- Adds migration `003_build42_finance_boost.sql` and compatibility for importing older SQLite baselines and Build 42 extension tables.

No Stripe sandbox account, Android APK, hosted Render revision or real-world payment test was available to verify here. This archive is a candidate pending those gates.
