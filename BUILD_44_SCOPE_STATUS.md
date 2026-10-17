# Build 44 scope and remaining boundaries

Implemented code is included in one shared-backend source bundle. Verification status is separate in TEST_RESULTS_BUILD_44.md; this is not a fully verified or launch-ready release.

| Agreed area | Included | Remaining limits |
|---|---|---|
| Admin active-trip map | Google Maps adapter, pickup/destination, driver and optional passenger positions, freshness/accuracy, role restrictions | Real Maps key and tiles need deployment acceptance; list capped at 100 |
| Saved routes and investigation | Trip GPS with observation/receipt times, navigation route snapshots, timestamp replay with gaps, event timeline, holds and sensitive-access audit | History begins with new uploads; legacy route-data retention still needs review |
| Pickup check-in | Sustained low straight-line progress triggers a check-in, driver reasons and Admin escalation | Not road-aware deviation or traffic-aware ETA detection; no onboard deviation/stoppage detector |
| Reassignment | Owner/Operations can return a pre-start ride to matching atomically, preserving fare and revoking the old assignment | Automatic reassignment is disabled; no automated earnings penalties |
| Documents | Driver uploads, Admin review, version history, configurable required kinds, expiry checks, renewal access and inbox | Records are keyed to driver/current vehicle; separate multi-vehicle records and eligibility switching are not implemented |
| Reminders | Configured expiry thresholds, deduplicated durable inbox, scheduler retries | No guaranteed offline push, SMS or email, delivery receipts or external notification provider |
| Active-trip expiry | Blocks further dispatch/start; allows an already-started trip to finish | Dedicated urgent operations workflow for expiry/revocation onboard remains to be added |
| Passenger safety | Expiring/revocable trip links; optional foreground location; saved local emergency contact and dialler | No emergency dispatch service; passenger background tracking deliberately absent |
| Data audit | Existing fares/finance/dispatch events preserved; new evidence, document versions and staff access audited | Separate immutable eligibility snapshots at every acceptance, complete legacy retention/deletion and regulatory reporting remain pending |

The remaining items above must not be described as completed. Budget constraints remain: no new paid services, live payouts, automatic loss-making promotions or uncapped incentives. Driver boost-map UI remains deferred.
