# Build 44 — Safety operations and document lifecycle

Passenger 0.36-build44 (47), Driver 0.21-build44 (43), Admin 0.11.0, API 44. Continues the authoritative Build 43 source.

- Live Admin Google Maps integration, driver freshness/accuracy, optional passenger GPS, pickup/destination, recorded trail/replay and route versions.
- Trip GPS evidence with original observation/receipt timestamps, bounded recovery buffer, access audits, retention and investigation holds.
- Low-progress pickup check-in, driver reasons and Admin escalation. Owner/Operations can atomically return a pre-start pickup to matching with a reason. No automatic reassignment, pay deduction or fare change.
- Document version history/downloads, reminders/inbox, required versus optional checklist, expiry enforcement and Driver access to submitted files. Existing active trips can finish; expired drivers cannot take new work/start another trip.
- Expiring/revocable trip sharing, consented foreground passenger location, local emergency-contact saving/dialling.
- Additive migration 004, existing accounts/database/financial behaviour preserved. Same shared backend/services.

See TEST_RESULTS_BUILD_44.md for actual executed checks. No cloud deployment, purchase, real payment or payout was performed. Boost spending remains controlled by existing disabled/capped configuration. The Driver boost map remains deferred, not silently represented as complete.

Read BUILD_44_SCOPE_STATUS.md for partial scope and TEST_RESULTS_BUILD_44.md for blocked compilation/runtime gates. This candidate is not a claim that every planned workflow is complete.
