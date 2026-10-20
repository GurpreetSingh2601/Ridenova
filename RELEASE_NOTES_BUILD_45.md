# Build 45 release notes

- Shared server pickup road distance/traffic ETA, cached and rate-capped, used by the offer card and pickup preview geometry.
- Labelled development fallback; staging offers fail closed when routing is unavailable. Configurable road distance/time dispatch limits.
- Assignment-level engaged-time accounting covering pickup, waiting, trip, cancellation, no-show and reassignment. Duplicate lifecycle actions do not duplicate records.
- Integer-cent estimates separating base earnings, mileage and bonus; hourly earnings exclude mileage reimbursement.
- Vancouver semimonthly pay-period reporting, effective-date policies, per-driver floor reconciliation, verified-distance review and idempotent closed-period test ledger finalization.
- Driver pay-period view with prior/next period navigation, explicit review state and test-only status.
- Capped boost-zone map circles, details, expiry, category restrictions and highest-single-bonus rule. Atomic acceptance reservation and cancellation release.
- Admin Finance compensation investigation, estimated/recorded comparisons, audited distance review, policies and period finalization. Existing trip evidence and lifecycle timeline remain in Operations.
- Restore pickup figures/compensation with active trips. Clear stale offers on failed fetch. Preserve existing GPS queue, background recovery, waiting timers and server-authoritative state polling.
- Passenger ETA source labelling and fresh-GPS pickup ETA updates.
- Consistent Build 45 labels, new Android version codes, API health version, Admin 0.12.0, CI and migration/import integration.

No live payments/payouts, provider accounts, promotional budget, secret values or deployment changed. See scope and test results for limitations.
