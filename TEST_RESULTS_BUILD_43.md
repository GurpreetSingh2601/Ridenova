# Build 43 verification results

## Executed and passed

- **164 backend regression tests**, full unittest discovery. Actual output: `verification/build43-portable-tests.txt`.
- Admin HTML structure, all seven inline JavaScript syntax checks, source/navigation/version assertions and Compliance paginator restriction. Included in the portable log.
- Android XML/Gradle/Kotlin source preflight. This is not compilation or device testing.
- **23 PostgreSQL tests** passed earlier in this task. See `verification/build43-postgres-results.md` for the observed result, precise coverage and later repeat limitation.
- Admin Chromium regression: nine workspaces, Owner + four restricted roles, desktop/mobile, escaped pickup instructions, no-show details, session expiry, logout races, refresh failure and coalescing. Actual output: `verification/build43-admin-browser.txt`; synthetic render evidence: `verification/ui-evidence/`.
- Two-worker Gunicorn health/Admin CSP, sign-in, authenticated access and session persistence across worker restart. Actual output: `verification/build43-gunicorn-smoke.txt` (SQLite transport smoke).
- Database compatibility: existing migrations 001–003 are byte-for-byte unchanged. See `verification/build43-database-compatibility.txt`.

## Android compilation gate

**All four assemblies passed:** Passenger `assembleDebug` + `assembleStaging`, Driver `assembleDebug` + `assembleStaging`. Clean build logs: `verification/build43-passenger-gradle.txt` and `verification/build43-driver-gradle.txt`. After the final receipt wording adjustment, both Passenger variants were assembled again successfully: `verification/build43-passenger-final-gradle.txt`. Compilation uses no real Maps key and an intentionally invalid staging origin, so test artifacts are not installable release APKs for your service. Existing deprecation warnings are not compile errors. Gradle staging lint-vital tasks executed as part of assembly; no full Android lint or emulator/device UX pass is claimed.

## Requires your configured environment

Real Android device testing, Maps/Places behavior, keyboard/insets/accessibility, foreground/background GPS and reconnection; authorized deployment of the same commit to existing Render services; hosted speed/freshness; real Stripe test-provider verification. Use the single manual checklist. No public-launch approval, real charge or payout is asserted.

## Release archive verification

The packaging command checks required files, one shared backend, short archive paths, unique inventory, every SHA-256 entry and ZIP CRC. Actual outcome is included in `verification/build43-package-check.txt`. No private configuration, database, signing key or compiled APK is shipped.
