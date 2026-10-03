> Historical Build 42 record. For this release, read the root START_HERE_BUILD_42_1.md and TEST_RESULTS_BUILD_42_1.md.

# Build 42 acceptance checklist

- [ ] CI shared API, PostgreSQL integration and both Android jobs pass on the exact Git revision.
- [ ] Take an external database export; deploy Build 42 against the same Render DB. Confirm `/health` reports build 42; confirm existing Owner, Passenger and Driver accounts still sign in.
- [ ] Compare Render logs before/after: `durationMs`, `rateMs`, `lockWaitMs`, `handlerMs` on a slow app refresh. Note any 429/503 responses. No tokens or DB URLs in logs/screenshots.
- [ ] Add a Stripe **test** card using hosted checkout and Verify; repeat Verify and confirm one card. Existing display-only card cannot authorize.
- [ ] Book and complete a ride with the test card, authorize test fare twice, confirm one provider PaymentIntent, capture twice, confirm one ledger capture.
- [ ] Refund a partial test amount with a stable request key, repeat it, verify one refund; reject a conflicting amount or over-refund. Run Owner reconciliation and compare Stripe test dashboard.
- [ ] Owner can create disabled boost zone and enable it. Completing a qualifying ride adds one award; repeat completion does not. Budget cap blocks further awards. No passenger fare changes.
- [ ] Finance role can read finance and reconcile; cannot capture/refund/change zones. Support/Operations cannot see finance endpoints. Owner audit records mutations.
- [ ] On a real phone, test background/foreground refresh, map key, booking, ride completion and browser return. Verify Driver offer and status behavior on free staging with limitations understood.
