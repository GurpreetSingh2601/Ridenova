# Build 42.1 known issues and boundaries

1. **Phone acceptance is still required.** Both Android variants compile, but device rendering, keyboard resize, TalkBack, 150% font scale, map loading, GPS/foreground service behavior and OEM-specific back gestures have not been exercised here.
2. **Small screens may scroll.** Driver actions stay fixed, while details can scroll at large text sizes or short landscape heights. No claim is made that every possible font/screen setting fits every offer without scrolling.
3. **Hosted speed is unmeasured.** Admin now loads only the current workspace and reports freshness/failure. Android refresh cadence and the backend request serialization/rate gates are preserved. Render cold starts, database time and network latency still need measurement in your actual service.
4. **Staging access rules remain.** Invited testers are still required. Staging Driver signup/recovery is not enabled by this design update; development registration remains. Passenger/Driver public self-service onboarding and real SMS are not completed here.
5. **Payments are test-only.** Existing hosted checkout/authorize/capture/refund controls remain. `Authorized · awaiting capture` is an authorization state, not a completed capture. Live charges and payouts remain disabled. No new provider credentials are included.
6. **Existing placeholder features are not upgraded into services by styling.** Real payouts, production identity verification, support delivery guarantees, push/calling/messaging, full multi-stop/scheduled operations and later safety/boost-map work remain governed by the roadmap.
7. **Admin deployment testing remains.** Automated rendering uses fixture responses; test your actual Owner and staff accounts after deploying. Finance still receives addresses where existing backend permissions allow ride reads. No permission expansion was made.
8. **Your infrastructure topology remains yours.** This ZIP does not create a scheduler, enable backups, change Render plans or alter invitation secrets. Keep the configuration that is already working. A preview without a continuous scheduler is not equivalent to a fully operational dispatch deployment.
9. **Older trip data is not invented.** Missing historic route/address/earnings fields cannot be reconstructed accurately by UI changes alone.
10. **No production approval.** BC regulatory, insurance, privacy, tax and operational readiness require the agreed later checks and professional review where appropriate.

Current automated results and exact limits are recorded in `TEST_RESULTS_BUILD_42_1.md`. No new database migration is required when upgrading the corrected Build 42 schema.
