# One integrated Build 41 acceptance checklist

Run after automated PostgreSQL/Android gates pass and staging deployment is authorized.
Record commit, device/OS versions, dates, results and request IDs for failures.

- [ ] `/health` identifies Build 41/staging and the deployed commit; `/ready` is 200.
- [ ] Passenger and Driver staging Maps load with their new package restrictions.
- [ ] Passenger on mobile data, Driver on another network, Admin on PC: all use the
  same hosted API with the laptop backend stopped and no ADB reverse.
- [ ] Invited Passenger can sign in using privately provided code; unknown phone,
  development OTP and stale/revoked session fail. No code appears in API responses.
- [ ] Provisioned Driver signs in, submits sample documents, obtains Admin approval,
  goes online and publishes location. Signup/recovery explains staging restrictions.
- [ ] Owner creates restricted staff; each sees permitted workspaces only. Compliance
  can review documents without receiving ride lists; Support cannot access finance;
  Finance cannot modify drivers. Disabled/logged-out sessions fail server-side.
- [ ] Selected road route, distance, ETA, GST and quote total stay consistent through booking.
- [ ] Two nearby eligible drivers see radar; simultaneous accept yields exactly one
  assignment. Decline stays suppressed; untouched/expired radar falls back correctly.
- [ ] Arrival → PIN/start → complete stays synchronized; ratings, route history,
  earnings and Admin events appear exactly once, including repeated button actions.
- [ ] Disable network immediately after Confirm/Accept; reconnect/reopen apps and
  recover the original ride. No duplicate booking, assignment or earning appears.
- [ ] Background/foreground and screen-lock Driver tests keep expected GPS behavior;
  stale/offline drivers stop receiving new offers. Passenger progress recovers.
- [ ] Restart API/worker during a test ride; recover that ride and sign-in state.
- [ ] Stop scheduler: `/ready` becomes 503 within 45 seconds and configured alert
  reaches the operator. Restart same revision and confirm recovery.
- [ ] Rehearsed SQLite import preserves representative users/trips/documents/ledger;
  original stays unchanged; new sign-in is required; drivers start offline.
- [ ] Backup and separate-database restore drill match manifests; record actual
  restore time and backup age. Reject occupied restore/import targets.
- [ ] Rehearse compatible code rollback on staging; both services match revision,
  migrations remain compatible, and no post-backup rides are silently lost.

No need to test intermediate patches. Complete this checklist once against the
integrated candidate after blockers are resolved, then decide Build 41 acceptance.
