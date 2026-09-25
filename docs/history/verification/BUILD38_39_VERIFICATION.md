# Build 38/39 verification

- Source baseline: Build 38 Passenger recovery hotfix, as delivered following Build 36.
- Backend automated tests: 121 passing (`python -m unittest discover -s backend -p "test_*.py"`), including new role checks, revocation, paging/filtering and matching-preservation regression suite.
- Admin JS: `node --check` on concatenated inline scripts: PASS.
- Driver Android Gradle compile: NOT VERIFIED. Gradle wrapper distribution (9.6.0) unavailable in this container; `services.gradle.org` could not be resolved.
- Browser visual/interactive and Windows/physical Android tests: NOT VERIFIED here. User must run device acceptance checklist.
- Existing backend suite reported some connection ResourceWarnings; do not interpret test pass as exhaustive production validation.
- Server default remains loopback-only development mode. No public deployment, MFA, real payouts or legal driver identity verification implemented.
