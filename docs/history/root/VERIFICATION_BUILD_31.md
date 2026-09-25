# Build 31 verification

This is a UI development **source build**, not a fully tested Android release. No APK is included.

| Check | Current result |
|---|---|
| Shared backend regression/integration | 90 tests passed, rerun from this Build 31 bundle |
| Java scheduling | 9 checks passed after compilation/execution |
| Python syntax | All bundled Python files parsed successfully |
| Admin JavaScript syntax | Both inline scripts passed Node syntax checks |
| Android compilation/lint | Blocked: no cached Gradle distribution or Android SDK; Gradle bootstrap failed with `Network is unreachable` |
| Driver/Passenger UI | Source reviewed; NOT rendered or executed on Android here |
| Google Maps / Routes | Runtime unverified; requires the user's configured key and enabled APIs |
| ZIP | CRC, file-hash manifest and Build 30 file-retention checked before delivery |

The 90 backend tests do not validate Kotlin types, Compose measurements, touch interaction, Maps keys, route requests or keyboard behavior. Previews included in DriverApp.kt use real empty-state components but have not been rendered here. The new UI should be compiled and exercised on the Pixel before treating this as an accepted release.

## Reproduce

- `python RUN_TESTS.py` runs backend tests using temporary databases.
- `powershell -File VERIFY_ANDROID.ps1` compiles and lints both Android apps on a configured machine.
- `DEVICE_ACCEPTANCE.md` covers this build's runtime scenarios.
- `UI_REVIEW_BUILD_31.md` records the source audit and intended behavior.
- `verification/build31-*` are current logs. Earlier logs and `VERIFICATION_BUILD_29.md` / `VERIFICATION_BUILD_30.md` are historical.

The verification folder is optional evidence: users do not need to edit it or launch another server. Admin 0.3 and backend API 30.0 are deliberately unchanged; the original one-server architecture, accounts, documents, dispatch and data remain.
