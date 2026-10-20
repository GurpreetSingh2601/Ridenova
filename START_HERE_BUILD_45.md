# RideNova Build 45 — Trip accuracy, driver pay and reliability

This is a source staging candidate. It contains both Android apps, Admin and ONE shared backend in Passenger/backend. No deployment, live charge or driver payout was performed. Read TEST_RESULTS_BUILD_45.md before installing.

## Install from a short Windows path

1. Extract RN45 to `C:\RN45` (avoid nested long Downloads paths).
2. Keep a backup of Build 44 and its database. Preserve your private `Passenger/local.properties` and `Driver/local.properties` separately; copy them into the new matching projects. Do not commit them. Do not replace your real API URL or restricted Maps keys with example values.
3. In CMD:

```bat
cd /d C:\RN45
python VERIFY_BUILD_45.py
cd Passenger
gradlew.bat assembleDebug assembleStaging
cd ..\Driver
gradlew.bat assembleDebug assembleStaging
```

If your staging URL is not in each project's private properties file, configure `RIDENOVA_STAGING_API_BASE_URL` there before compiling. Open Passenger and Driver as separate Android Studio projects. Both use the same API. Run the phone checklist before inviting more testers.

## New server routing setup

The server must own the pickup road estimate. Set `RIDENOVA_ROUTES_SERVER_KEY` privately in your existing backend environment. It must be a server credential permitted to call Google Routes API; do not reuse an Android-restricted credential on the server. Keep it out of Android, Git and logs. No new provider account, billing or key was enabled by this build. Review your existing Google quota/billing controls before enabling calls.

- Staging fails closed for new offers when road routing is unavailable. Development can show a clearly labelled straight-line fallback; it is not a road ETA.
- Default staging maximum pickup: 15 road km / 30 minutes. Development: 50 km / 60 minutes.
- `RIDENOVA_MAX_PICKUP_KM` and `RIDENOVA_MAX_PICKUP_MINUTES` override these limits. To repeat the 37 km / 38 minute BC Place test deliberately, use 50 and 60 in the test environment, then restore your chosen operating limits.
- `RIDENOVA_ROUTE_CALLS_PER_MINUTE` defaults to 30 per API process. Cached routes last up to 30 seconds while the driver remains within 100 metres of the route origin. Google-side quota limits remain necessary across multiple processes.
- An offer freezes its route and payment estimate for the offer lease. Acceptance rechecks availability, location and bonus budget. An active pickup updates the passenger ETA from subsequent fresh driver GPS.

## Database and deployment

Existing migrations 001–004 are unchanged. PostgreSQL adds `005_trip_compensation.sql`. Back up and test a database copy first. Run the existing migration/deployment workflow; API and scheduler must run the same revision. The GitHub verification workflow now invokes VERIFY_BUILD_45.py and includes the new tests in PostgreSQL integration.

SQLite creates the new tables additively on startup. Historical trips are preserved; their unrecorded engaged kilometres are not invented. Finish active Build 44 rides before switching versions. Build 45 does not backfill missing compensation for older rides.

## Compensation workflow

- Offers separate base earnings, mileage allowance and the highest eligible single boost. The displayed hourly estimate excludes mileage allowance.
- Acceptance starts an assignment record. Waiting counts toward its elapsed time. Completion, passenger cancellation, driver cancellation, no-show and Admin reassignment close it.
- GPS samples produce a provisional distance observation. They are not a certified road odometer. ALL closed assignments require evidence-based actual-distance verification in Admin → Finance → Driver compensation before a pay period can be finalized. Use recorded evidence/odometer records; never approve the estimate as if it were actual mileage.
- Periods are the 1st–15th and 16th–month-end in America/Vancouver. Minimum-wage adjustments reconcile earnings (including bonuses, excluding mileage) per driver, per period. Rates are versioned by effective date. Current seeded rate: $21.89/hour and $0.45/km from June 1, 2026.
- Cross-period/rate-boundary assignments split time exactly and allocate distance/earnings proportionally by elapsed time. The screen flags this for review; this allocation policy requires payroll acceptance before commercial use.
- Finalization writes immutable, idempotent TEST ledger adjustments. No payout is sent. Finalized records cannot be overwritten; post-finalization payroll correction tooling is not included.
- Tips remain zero unless a future verified gratuity settlement integration records them. This build does not introduce live tipping or tax statements.

## Boost zones

Use the existing Admin Finance controls to create a disabled, capped platform-funded zone. Enable it only with an intentional test budget. Driver map circles show category, expiry and conditions. Eligibility uses pickup location, category and acceptance time. Highest bonus wins; overlaps do not stack. Budget is reserved atomically at acceptance, honored on completion even after expiry, and released on cancellation/reassignment. Accepted passenger prices do not change.

## Next step

Run the local tests/builds, configure the server routing credential, deploy to staging only after CI passes, and follow MANUAL_TEST_CHECKLIST_BUILD_45.md on both phones. This release is not commercial-launch approval.
