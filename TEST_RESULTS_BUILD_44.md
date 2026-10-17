# Build 44 verification — 2026-10-08 UTC

This is a source staging candidate. Android compilation and PostgreSQL integration have NOT passed in this environment. Do not merge/deploy until the included CI gates pass. No hosted service, real payment, payout or paid plan was changed.

| Check | Actual result | Evidence |
|---|---|---|
| Portable verifier after final backend correction | PASS: 185 backend tests, Admin syntax/source tests and Android source preflight | verification/build44-portable-tests.txt |
| Build 44 targeted tests | PASS: 21 tests, including pre-assignment GPS isolation | verification/build44-targeted.txt |
| Prior migrations preserved | PASS: 001–003 byte-identical to the delivered Build 43 ZIP | verification/build44-migration-baseline.txt |
| Final archive inventory, checksums and CRC | See successful packaging report | verification/build44-package-check.txt |
| Android Passenger and Driver staging compile | BLOCKED: Gradle download fails with network unreachable; Android SDK is absent. Earlier checkpoint logs also show missing SDK license/platform. No compiled APK supplied. | verification/build44-passenger-current-gradle.txt; verification/build44-driver-current-gradle.txt |
| Admin browser rerun | BLOCKED: Playwright browser executable absent; prior checkpoint recorded a passing synthetic browser run, not a current rerun or live Maps test | verification/build44-admin-browser-current.txt; prior verification/build44-admin-browser.txt |
| PostgreSQL runtime/concurrency/restore | NOT RUN: PostgreSQL server and psycopg unavailable. CI includes migration 004 and Build 44 tests; corrected migration-count assertion from 3 to 4. | verification/postgres-integration.py |
| Prior SQL syntax and Gunicorn checks | Retained checkpoint evidence only; not rerun here | verification/build44-postgres-syntax.txt; verification/build44-gunicorn-smoke.txt |
| Physical phones, real Maps key, Render connectivity/load | NOT RUN; acceptance required | MANUAL_TEST_CHECKLIST_BUILD_44.md |

Source checks are not Kotlin compilation. SQLite concurrency tests do not establish PostgreSQL correctness. Existing browser screenshots contain synthetic fixtures.

Final correction: GPS observed before the current assignment is rejected even when an upload omits its ride ID. Such samples cannot change the new trip trail or live availability. The added regression also runs through the PostgreSQL test subclass in CI.
