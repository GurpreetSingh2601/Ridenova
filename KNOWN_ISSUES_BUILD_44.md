# Build 44 limitations / release gates

- Physical Android acceptance, live restricted Google Maps key/tiles, deployed Render performance and cross-network tests remain required. Browser fixtures are synthetic.
- PostgreSQL execution/locking/restore is a required CI gate. SQL parsing and SQLite tests do not substitute for it; see actual test results.
- Monitoring detects sustained low straight-line progress to pickup, not precise turn-by-turn deviation, intent, fraud or misconduct. Human review is required. No automatic reassignment or financial penalty.
- Inbox reminders and foreground notification are implemented; guaranteed offline push/SMS/email waits for the communications milestone. Continuous cleanup/reminders need the existing scheduler. Android force-stop/permission denial cannot be bypassed.
- Driver GPS buffer is 900 points/24h; old missing data cannot be recreated. Passenger tracking is optional, foreground active-trip screen only; public links show driver position only.
- Live Admin list capped at 100; evidence pages 1,000 points. Large-scale indexing/streaming/load tests remain future work. Hidden-tab refresh pauses.
- Legacy provider data/backup/account deletion retention requires further review. New navigation snapshots expire after 30 days even under holds.
- Document authenticity, regulatory approval, RCC issuance, company-document distribution, offline legal document access, daily inspections and provincial reporting are not certified/automated by this build. Current submitted files can be viewed from Driver. Professional compliance review remains mandatory before commercial operation.
- Stripe stays test-only. No new real charges/payouts or incentive budget. Driver boost-map UX remains explicitly deferred.

See BUILD_44_SCOPE_STATUS.md for agreed items that are only partially implemented, including road-aware monitoring, multi-vehicle document records and external reminder delivery.
