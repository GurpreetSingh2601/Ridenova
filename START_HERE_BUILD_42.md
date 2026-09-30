# RideNova Build 42 — sandbox and boost staging candidate

This archive contains Passenger Android, Driver Android, Admin and **one shared backend**. It includes the Build 41 staging payment query fix. This is a test-only candidate, not an approved public launch.

## Update your existing project safely

1. Back up your current Git working tree and confirm your Render database has a recoverable external `pg_dump` export. Do not delete or replace the existing database.
2. Extract this ZIP to a short path such as `G:\RideNova\RN42`. Copy the **contents** into your existing Git checkout, retaining your local untracked `local.properties` and `gradle.properties` values. Do not copy a blank database; none is included.
3. Review `git diff`, especially the additive `003_build42_finance_boost.sql` migration. Commit and push the code. Wait for all three GitHub verification jobs. They should run PostgreSQL integration and both Android compilations; this workspace could not execute those gates.
4. In Render web-service Environment, add `RIDENOVA_STRIPE_TEST_SECRET` with your **Stripe test secret key** (`sk_test_…`) only when you have a Stripe sandbox account. Never paste it into Git, Android, screenshots or messages. The Build 42 backend rejects live keys. If not set, existing simulated card flow remains, and Stripe features return `SANDBOX_UNAVAILABLE`.
5. Deploy the exact verified commit to the **existing** Render API service. Its start command runs versioned migration `003` before Gunicorn. On the paid topology, use the existing pre-deploy migration. Do not redeploy the Blueprint merely to add this environment variable. Check `/health` shows build 42; `/ready` depends on a working scheduler and stays 503 on the free single-service preview.
6. Rebuild **Passenger staging** (`assembleStaging`) and **Driver staging** with your existing `RIDENOVA_STAGING_API_BASE_URL` and Maps setup. Install the new Passenger staging APK. Driver has a build/version bump but no new screen. No Owner or Driver account bootstrap is required when using the same Render PostgreSQL database.
7. In Passenger → Payment methods, tap **Add Stripe test card**. Complete the Stripe hosted test form, return to RideNova, then tap **Verify test card after checkout**. Use Stripe's documented test card details, never a real card. Select the test card *before* booking a new ride. In completed Trip details, tap **Authorize test payment**. As Owner in Admin → Finance, inspect, capture, refund using a stable request key, and reconcile.
8. In Admin → Finance, Owner can create a disabled boost circle (centre, radius, category, time window, bonus, total budget) and enable it. Complete eligible test rides to see one award per ride and budget consumption. Driver map/earnings bonus display is planned for Build 43.

## Important boundaries

- These are **Stripe test** transactions only. The release rejects `sk_live_` keys, production backend mode is disabled, and payouts are disabled.
- The existing development card display references are not Stripe payment credentials; bookings made with them cannot be authorized in Stripe. Existing rides and payment references remain intact.
- Test payment authorization is an explicit action **after completion**. Failed provider requests can be retried with the same ride and Stripe idempotency key. An uncertain result needs Owner reconciliation before another action.
- Free Render Postgres has an expiry and no managed backups. Export test data regularly; do not use real passenger/driver data or production payments.
- No continuous worker on the free preview means scheduled dispatch and offer expiry are not reliable. This is not an operationally complete Build 41/42 deployment.
- See `TEST_RESULTS_BUILD_42.md`, `KNOWN_ISSUES_BUILD_42.md`, `STAFF_PERMISSIONS_AND_TESTING.md` and `RIDENOVA_DEVELOPMENT_RULES.md`.
