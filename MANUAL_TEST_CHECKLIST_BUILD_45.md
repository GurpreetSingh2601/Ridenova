# Build 45 phone and staging acceptance

Before testing: back up Build 44/database, finish existing active rides, use Stripe test settings only, ensure both apps use the same staging API, configure server Routes key, check /health build 45 and /ready.

1. BC Place: allow a long pickup deliberately in test limits; compare server road km/min with the same origin/destination in Maps at the same time. Confirm offer preview and card use one snapshot. Compare total distance/time and earnings/mileage/bonus arithmetic.
2. Missing routing: remove the test server route credential or simulate provider failure. Staging must not offer an approximate trip. Development must label the fallback. Restore the credential.
3. Limits: a road detour beyond the configured pickup limit must not dispatch, even if the straight-line distance is close. Test nearby eligible driver and stale GPS separately.
4. Offer: large fonts, small phone, landscape, expiry timer, scrolling and reachable accept/decline. Disconnect while an offer is visible; do not leave a stale actionable request.
5. Active pickup: drive a safe test route as a passenger observes ETA; verify fresh/old GPS display. Confirm arrival and waiting state. Do not interact while driving.
6. Recovery: restart both apps during pickup, waiting and trip; temporarily disconnect/reconnect. Same assigned ride, no duplicate booking, restored driver details and server-authoritative state.
7. Compensation: accept → pickup → wait → start → complete. Compare actual time and verified mileage with Admin. Verify cancellation, no-show, driver cancel and Admin reassignment preserve each driver's accepted work.
8. Distance gaps: disable GPS temporarily. Admin must show review required. Finalization must remain blocked until actual distance is reviewed with an evidence-based reason.
9. Pay periods: use synthetic closed-period fixtures. Confirm earnings, bonus, mileage and top-up separately; retry finalization and confirm exactly one ledger adjustment. Cross-month/DST and cross-period allocations need payroll review.
10. Boosts: create capped disabled zone; enable intentionally; verify matching category map circle, expiry and rules. Two drivers competing for final budget must not both reserve it. Check cancellation release, completion after expiry and highest-only overlap.
11. Passenger fare: acceptance/completion/boost/reassignment must not silently increase the accepted passenger price.
12. Admin permissions: Finance can read; only Owner writes review/policy/finalization. Support/Operations cannot access compensation API. Logout during fetch must clear old data.
13. Verify Build 45 in Driver drawer, Passenger version information, Admin header, /health and START_HERE. Preserve private properties; inspect Git diff before staging selected files.

Record device model, build variant, test time and pass/fail for each. CI and phone acceptance are separate from the portable Python/source checks.
