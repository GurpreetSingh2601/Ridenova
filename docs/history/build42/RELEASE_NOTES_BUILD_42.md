> Historical Build 42 record. For this release, read the root START_HERE_BUILD_42_1.md and TEST_RESULTS_BUILD_42_1.md.

# Build 42 release notes — staging candidate

Passenger `0.34.0-build42` (44), Driver `0.19.0-build42` (40), shared API `42.0`, Admin `0.9.0`.

- Bundles Build 41 PostgreSQL payment-method order fix.
- Batches staging request rate checks in one PostgreSQL transaction and logs `rateMs`, `lockWaitMs`, `handlerMs` to isolate the 650–2200 ms API latency shown in Owner's Render screenshot. The request gate remains conservative for correctness. No speed improvement is claimed before hosted measurement.
- Adds Stripe **test-mode-only** hosted card setup, completed-trip manual authorization, Owner capture/refund, test finance ledger and provider reconciliation. Production mode and payouts remain disabled.
- Adds owner-configured, disabled-by-default capped platform-funded boost circles. Completion awards once within budget, without changing accepted passenger fares.
- Adds an Admin Finance workspace and Passenger staging test-card flow; preserves staff role restrictions and existing data.
- Adds migration `003_build42_finance_boost.sql` and compatibility for importing older SQLite baselines and Build 42 extension tables.
- Corrects the PostgreSQL CI finance fixture to use explicit staging settings with its fake Stripe provider. Awaiting the fresh GitHub CI result.
- Normalizes PostgreSQL driver balance totals to integral cents before serializing the Admin Finance summary. Adds a decimal balance regression and PostgreSQL summary serialization check. Awaiting CI and hosted confirmation.

The Owner reported successful Stripe sandbox setup and authorization returning `requires_capture` on the earlier hosted revision. This corrected archive remains a candidate pending fresh PostgreSQL CI, hosted Admin Finance recheck, and Android device verification.
