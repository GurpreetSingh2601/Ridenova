# Build 45 scope and acceptance status

| Area | Implemented | Acceptance / remaining limits |
|---|---|---|
| Pickup routing | Server Google Routes adapter; offer snapshot and matching preview; source labels; road-based limits | Server key/quota setup and live traffic acceptance required. Three-second provider timeout; calls occur under existing serialized staging dispatch. |
| Compensation | Assignment tracking; cancellation/reassignment closure; cents; effective-date rates; period floor and mileage; audited review and test ledger finalization | Actual distance requires manual verification for every assignment. No automated certified odometer, historical backfill or post-finalization correction workflow. |
| Offers | Base, mileage, bonus and total; hourly earnings exclude reimbursement | Physical small-screen/large-font check required. Estimated period top-ups are separate from the per-offer total. |
| Passenger pickup | Road-based live ETA after fresh GPS; approximate label on fallback; existing arrived state | Map navigation may choose a newly calculated route; traffic can change between refreshes. No guaranteed arrival time. |
| Reliability | Existing recovery/wait/no-show/GPS buffer retained; restored figures fixed; failed offer fetch clears stale offer | Force-stop, offline push and external notifications remain out of scope. Render cold starts are not removed by this build. |
| Driver earnings | Current and previous pay-period summary; trip earnings history remains available | Daily history is base earnings for completed trips, not a full payroll statement. Pay-period section is authoritative for this build's compensation records. Tips not integrated. |
| Admin investigation | Compensation table, estimate-vs-recorded figures, distance review, effective rates, immutable period finalization | Trip route/event evidence remains in Operations using the same ride ID. No automatic financial penalties. |
| Dispatch | Fresh GPS and existing atomic eligibility checks plus route limits | Default staging 15km/30min. No automatic passenger price increase or production profitability guarantee. |
| Boost map | Eligible active circles, bonus/expiry/conditions, reservation and completion award | No zone activated or funded. Google map/device acceptance still required. No stacking. |
| Versions and delivery | Both apps, one API, Admin and docs identify Build 45 | Android binaries not compiled here; source candidate only. |

Commercial release remains blocked by external build/runtime/device verification and qualified BC payroll/regulatory review. The source package is reviewable and testable, not a certification of compliance.
