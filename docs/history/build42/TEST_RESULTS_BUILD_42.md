> Historical Build 42 record. For this release, read the root START_HERE_BUILD_42_1.md and TEST_RESULTS_BUILD_42_1.md.

# Build 42 verification record

- `python VERIFY_BUILD_42.py`: re-run after the finance summary correction; 153 backend tests passed, Admin HTML/Node syntax/source checks passed, and Android source delimiters/manifests passed.
- `python verification/admin-preflight.py`: 6 inline scripts parsed with Node.
- `node verification/admin-source-test.cjs`: navigation, role-gated source and syntax passed.
- Targeted test coverage in `Passenger/backend/test_build42.py`: fake Stripe test card ownership, retry, capture, refund, reconciliation, role boundaries, rate-check batching, boost budget and duplicate completion.
- Android Gradle: attempted offline Passenger and Driver; blocked before project compilation because `gradle-9.6.0-bin.zip` was unavailable and distribution network was unreachable. No APK is claimed.
- PostgreSQL disposable integration: not run locally (no PostgreSQL or psycopg). The finance/boost persistence test now also checks that the Finance summary is JSON serializable with a populated driver balance. GitHub `shared-api` is the required gate for the new revision; no PostgreSQL pass is claimed locally.
- Owner observed Stripe sandbox setup and completed-ride authorization returning `requires_capture` on Render. Admin Finance `/summary` then returned 503 while `/zones` returned 200. Source analysis identifies PostgreSQL `SUM(BIGINT)` returning NUMERIC/Decimal in a populated balance, causing JSON serialization to fail. The conversion fix passed the portable regression suite but requires fresh PostgreSQL CI and hosted recheck. No live charges were attempted.
