# Build 42.1 verification record

Executed against this source revision on 2026-10-03 UTC. Earlier Build 42 records are historical and are stored separately in `docs/history/build42/`.

| Check | Actual result | Evidence |
|---|---|---|
| Portable backend regression | **153 tests passed** | `verification/build42_1-portable-tests.txt` |
| Admin structure and JavaScript | All **7** inline scripts parsed; navigation/source checks passed | Same portable log |
| Android source preflight | Both manifests and source/configuration checks passed | Same portable log; not a substitute for compilation |
| PostgreSQL 16.15 integration | **12 tests passed** | `verification/build42_1-postgres-tests.txt` |
| Real Gunicorn transport | Two workers, health, Admin CSP, sign-in and persistence after restart passed | `verification/build42_1-gunicorn-smoke.txt` |
| Admin Chromium browser | Nine workspaces, Owner + four restricted roles, keyboard interaction, empty search, refresh failure/coalescing, mobile overflow, logout race and 401 clearing passed | `verification/build42_1-admin-browser.txt` |
| Passenger Android | **assembleDebug and assembleStaging succeeded**; code 45 | `verification/build42_1-passenger-gradle.txt` |
| Driver Android | **assembleDebug and assembleStaging succeeded**; code 41 | `verification/build42_1-driver-gradle.txt` |
| Release archive | CRC, unique paths, required files and SHA-256 inventory checked | `verification/build42_1-package-check.txt` |

## What these checks covered

The PostgreSQL suite used disposable UTF-8 databases, independent acceptance processes, shared radar claims, stale GPS, explicit declines, duplicate booking/completion persistence, migrations, SQLite import and occupied-target refusal, backup/restore checksums, financial/boost persistence and payment-method ordering. It also exercised JSON serialization of populated driver balances, preserving the latest finance fix.

Browser tests use the actual Admin HTML with synthetic API fixtures, not your live Render service. Rendered evidence is under `verification/ui-evidence/`; screenshots were inspected for desktop and 390px mobile layout. The role tests verify the UI; separate backend regression tests verify authorization. Fixtures are not production records.

Android compilation used the project's existing Gradle 9.6.0 / AGP 9.4.0 dependencies, full Java 17 and Android API 37 SDK. Tool download/certificate issues were resolved in the temporary build environment without changing the project's dependencies. A Driver preview callback compilation error was fixed before the successful run. Both variants produced APK metadata with the intended versions. Internal APKs used `https://staging.example.invalid` only to validate compilation and are intentionally not shipped.

## Not executed or not established here

- No Android emulator/physical-device visual, TalkBack, keyboard or GPS test. Android Studio previews are provided where present; they are not rendered test evidence.
- No full Android lint or instrumentation-test claim. Compilation emitted deprecation warnings for existing Compose/icons APIs; no compilation errors remain in the verified builds.
- No Windows execution or extraction test. ZIP paths are kept short and checked by the packaging script.
- No live Render load test, latency benchmark, production-data restore or remote deployment.
- No new real Stripe sandbox call, real charge or payout. Financial regression uses the fake provider; repeat sandbox acceptance with your configured service.
- No iOS build, public-launch approval or legal/compliance certification.

## Reproduce

Run `python VERIFY_BUILD_42.py` from the root. For browser checks, run `npm ci`, `npx playwright install chromium`, then `npm run test:browser` from `verification`. Its test browser only loads local synthetic fixture URLs. The GitHub job also installs Linux browser dependencies.

PostgreSQL tests require two **disposable** databases whose names end in `_test`, supplied as `RIDENOVA_TEST_DATABASE_URL` and `RIDENOVA_TEST_RESTORE_DATABASE_URL`; never point them at staging or production. Matching PostgreSQL client tools are required. Run `python verification/postgres-integration.py` with the backend requirements installed.

For Android, use the same build commands in `START_HERE_BUILD_42_1.md`. Run `python verification/package-build42.py` to create and validate the final source ZIP. The older verifier/packager filenames are retained for command compatibility.
