# RideNova Build 40.1 — Admin JavaScript and Staff Page Hotfix

Based directly on RideNova Build 40 Integration Hardening Candidate.

## Fixes
- Repair malformed `id="staff-workspace hidden>` HTML that made the Staff & access node unfindable and crashed sidebar initialisation with `Cannot set properties of null (setting hidden)`.
- Guard Staff workspace initialisation so missing markup does not crash the entire navigation.
- Reference the ride paginator explicitly across inline script scopes. The previous missing Staff element prevented paginator initialisation, causing `loadPagedRides is not defined` on refresh.
- Update the static Admin masthead from Build 35 to Build 40.1.

## About HTTP 401
401 means the backend rejected the supplied token, often an old development token after an Owner account has been configured. Open the page and sign in with your Owner **username and password**. Avoid the legacy development token once staff auth is set up. Log out and sign in again if the staff session is expired. Do not delete your database or disable authentication.

## Installation
1. Stop your running backend. Back up your current SQLite database (do not replace or delete it).
2. Extract this ZIP to a NEW folder. Preserve your existing database and configuration and start the backend from the NEW folder; do not leave the previous build server running on port 8080.
3. Navigate to `/admin#staff`, hard-refresh (Ctrl+F5), sign in as Owner and verify Staff creation form and sidebar display. Then load Rides and Fleet.
4. If the page still says Build 35, verify that the running server points to the newly extracted Build 40.1 and that the browser cache is cleared.

## Verification performed
HTML staff form ID present, all five Admin inline scripts pass Node.js syntax checks, and ZIP integrity verified. Backend and Android regression tests are not claimed to have run in this patch.
