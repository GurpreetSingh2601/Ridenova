> Historical Build 42 record. For this release, read the root START_HERE_BUILD_42_1.md and TEST_RESULTS_BUILD_42_1.md.

# Build 42 limitations and follow-up

- Android Gradle compilation could not run here: Gradle 9.6 distribution was absent and external network access failed. GitHub Actions/Windows compilation and device tests are required.
- PostgreSQL integration could not run in this workspace (no local PostgreSQL or psycopg). CI must verify additive migration, import, concurrent dispatch and restore against disposable PostgreSQL.
- No Stripe test key was available. Provider interactions are automatically tested with a fake that models test responses; real Stripe test-mode API and checkout remain unverified.
- Stripe setup uses the hosted browser and manual “Verify test card” return action. It does not automatically deep-link back into the app.
- A test authorization is deliberately requested only after a completed test ride. Booking-time authorization, payment failure recovery involving a different card, webhook delivery and production charge lifecycles require further development.
- Stripe refund/pending outcomes require Owner reconciliation. The sandbox finance ledger is not an actual settlement statement and no driver payout executes.
- Admin driver balances are provisional gross before costs and payout review; refunded rides do not yet adjust driver compensation. They cannot be transferred or treated as a payable amount.
- The performance trace improves diagnosis and removes one connection per request, but free Render may remain slow due to its database size and serialized request gate. Measure hosted timings before altering concurrency safeguards or spending money.
- Free Render preview lacks scheduler and reliable unattended dispatch. Free Postgres expires after 30 days and has no managed backups.
- Boost evaluation uses requested pickup/time and selected category; boost map, driver bonus display, advanced eligibility and payout reconciliation remain planned for Build 43 and later.
