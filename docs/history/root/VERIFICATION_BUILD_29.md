# Build 29 verification record

Tested September 18, 2026. This ZIP is a development source release, **not a claim of complete device or production validation**.

| Check | Result |
|---|---|
| Python backend regression suite | **73 tests passed**, including all 52 inherited tests and 21 Build 29 tests |
| Fleet Android API contract over local HTTP | Passed: register, upload, admin review, approval, availability, GPS, offer, accept, arrive, PIN start, completion, history, audit and auth isolation |
| Dispatch/lifecycle | Passed: nearest driver independent of polling order, categories, concurrent acceptance, expiry reassignment, stale GPS, busy drivers, cancellations, legacy/fleet exclusion, retry-safe completion and acceptance |
| Onboarding and migration | Passed: document validation, revision conflicts, rejection/resubmission, expiry, profile re-review, suspension, token reset, Build 28 document-table migration and active-ride recovery |
| Driver Android | **Final source compiled and packaged successfully** with `:app:assembleDebug`; `:app:lintDebug` passed with zero errors |
| Passenger Android | **Not fully compiled or lint-verified here**; the online build was interrupted by a policy-blocked Google Maven request; offline retry lacked dependency artifacts including Kotlin stdlib JDK8 and coroutines Play Services |
| Java scheduling checks | **9 checks passed**, compiled and executed with JDK 17 |
| Admin JavaScript + live backend | Passed in jsdom: dashboard, search, safe text rendering, four document reviews, approval/suspension, CSV export; no script errors |
| Full-browser visual checks | Not completed: Chromium launch was blocked by the runtime's socket restriction. DOM tests do not establish visual correctness |
| Physical phones / emulator | Not performed; no user devices, Maps credentials or active Android emulator available |
| Source preservation | All **104 original files retained**; 87 unchanged and 17 modified, plus new implementation/tests/docs/wrappers |
| Distribution | ZIP CRC integrity and per-file SHA-256 manifest checked before delivery |

## Android build details

Driver final command: `gradle --offline :app:assembleDebug :app:lintDebug`.
Final result: `BUILD SUCCESSFUL in 57s`; 48 actionable tasks, 13 executed, 35 up-to-date. The final compile includes the acceptance-response recovery and profile changes. The generated debug APK was for compilation verification only and has no personal Maps key; rebuild in Android Studio with your settings. APKs/build caches are excluded from the source ZIP.

The original dependency versions are preserved. Gradle wrappers were added, and their Gradle 9.6.0 distribution SHA-256 is pinned. Maps calls and actual road routing were not exercised. Driver lint still reports non-blocking warnings, including older dependency versions, unused resources and style suggestions; see the included lint report. The Android 26–27 signing-certificate flag warning was fixed in both apps.

Passenger's original Kotlin/Compose/Places dependencies could not all be downloaded in this environment. This is an unresolved verification limitation, not evidence of a successful Passenger build. Run `gradlew.bat :app:assembleDebug :app:lintDebug` in the Passenger project on your connected development machine before installing it.

## Reproduction

- Run `python RUN_TESTS.py` from any directory using its full path, or from this ZIP's root.
- Scheduling: compile `ScheduleTime.java` with `tests/ScheduleTimeTest.java` and run `ScheduleTimeTest` with JDK 17.
- Optional Admin tests: run `npm install` inside `verification`, then `python run_admin_ui_test.py`. This starts an isolated temporary backend on port 8099 using sample data.
- Build each Android project with the included Gradle wrapper; supply your SDK path/Maps configuration.
- Complete `DEVICE_ACCEPTANCE.md` on your actual phones, including background GPS, offline/reconnect, route display, document picking and all retained Passenger features.

## Scope limits

The backend remains the supplied local SQLite development server. No migration of a separate MySQL deployment, real identity verification, production driver authentication, payment capture, payouts, push delivery or public deployment was performed. Uploaded files receive bounded size, media signature, expiry and revision checks; there is no malware scanner or document authenticity service. Use sample documents only.
