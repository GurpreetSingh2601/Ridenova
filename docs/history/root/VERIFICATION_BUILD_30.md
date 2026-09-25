# Build 30 verification

This is a development source ZIP. It is **not fully device-tested or production-ready**.

| Check | Build 30 result |
|---|---|
| Backend regression and integration | **90 tests passed**: all 73 inherited tests plus 17 account/session tests |
| HTTP account flow | Passed: registration, sign-in, logout, sign-in-details retrieval and rejection of old session commands |
| Logout safety | Passed: goes offline, revokes token, releases offers, and rejects active-trip logout without destroying the session |
| Concurrency | Passed: duplicate username registration has one winner; logout/availability requests leave the old session revoked and offline |
| Account persistence/isolation | Passed: existing-profile setup, retained documents/history, different-account isolation and recovery of an active ride after server restart |
| Password/reset behavior | Passed: hashed password storage, normalized usernames, validation, bad-password lockout, admin reset, recovery credential rotation and suspension gating |
| Java scheduling | **9 checks passed** using JDK 17 compilation and execution |
| Python syntax | All backend modules compiled successfully |
| Admin JavaScript syntax | Both inline scripts passed Node syntax checks |
| Android compile/lint | **Not run for Build 30**: Android SDK and Gradle dependency cache are unavailable in this session |
| Android runtime / phone / emulator | **Not tested**: login/logout screens, lifecycle, secure storage, picker and background GPS need device verification |
| Admin browser rendering / DOM integration | **Not rerun for Build 30**; syntax checks do not establish visual correctness |
| ZIP | CRC, SHA-256 manifest and source-retention checks performed before delivery |

## What the test results do and do not prove

Backend tests exercise actual shared-database behavior and local HTTP requests. They do not execute Android UI code. Kotlin was reviewed, but Build 29's previous successful Driver compile does **not** certify the new Build 30 Kotlin changes. Passenger compilation was already incomplete in Build 29; it remains unverified here.

Run `VERIFY_ANDROID.ps1` on your configured development machine and complete `DEVICE_ACCEPTANCE.md`. No precompiled APK is supplied; build with your own Maps configuration and development signing key.

## Reproduction

- `python RUN_TESTS.py` from the extracted root runs the complete backend suite using temporary databases.
- `backend/test_build30.py` holds the new account/session tests.
- `verification/build30-backend-tests.txt` contains the current test output.
- `verification/build30-other-checks.txt` records the syntax and scheduling results.
- Other logs explicitly labelled HISTORICAL BUILD 29 were retained for reference only. `VERIFICATION_BUILD_29.md` is also historical.

## Implementation limits

The API remains a loopback SQLite development server with one currently valid session credential per driver. Passwords use PBKDF2-HMAC-SHA256 with a unique salt and 600,000 iterations. This is not a claim of independently audited production authentication: real identity verification, email/SMS password recovery, production hosting, payment processing and payouts are not implemented. Session credentials are revoked by logout, a subsequent sign-in, or admin reset; no scheduled session-expiry/refresh flow was added. Password recovery uses a trusted development admin.

Migration adds `fleet_logins` and `fleet_login_attempts`; existing driver credentials continue to work until sign-out/reset/new sign-in. The underlying shared API and database remain the same.
