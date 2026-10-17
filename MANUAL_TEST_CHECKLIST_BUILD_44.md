# Build 44 acceptance checklist

Use invited testers, synthetic documents and stationary/emulator GPS tests. Do not operate test controls while driving.

1. Verify CI, `/health` build 44, same accounts/database, both app updates and Admin role restrictions.
2. Book with edited pickup. Check quote distance/time/GST/fare, exactly one accepting driver, trip recovery, normal completion and inline ratings in both apps.
3. Admin → Live operations: select assigned trip; compare driver age/accuracy, pickup/destination, actual trail and planned route. Background Driver and check its ongoing location notification. Test permission/network loss and recovery without duplicate assignment.
4. Passenger → Safety & share trip: enable optional GPS. Confirm Admin sees it; turn off and verify removal. Background Passenger: no new passenger samples. Public sharing must never expose passenger GPS.
5. Open a share link on another device. Check destination/driver freshness, revoke/replace, then complete/cancel and verify invalidation. No phone/PIN should appear.
6. Simulate fresh, accurate, stationary GPS far from pickup for over three minutes. Driver gets check-in; traffic response acknowledges. Unanswered continued delay escalates, gaps reset observation. No automatic fee, deduction or reassignment.
7. Owner/Operations: enter reason and return pre-pickup ride to matching. Old driver loses assignment; new driver can accept; fare stays unchanged. Support cannot reassign/hold; a started trip cannot be reassigned.
8. Reopen completed trip in Admin, replay saved points, inspect timestamp/route versions and load further evidence. Gaps must not be drawn as continuous travel. Test hold/release with synthetic data.
9. Driver Documents: upload, review, replace, view archived revision in Admin and current submitted file on Driver. Confirm required/optional counts. Enable an extra test requirement and verify server-enforced eligibility until approval.
10. Use a controlled expired-document fixture: new offers/start blocked, inbox reminder visible, existing started trip still completes, earnings/support/renewal accessible. Renew/review and deliberately go online again.
11. Test refresh/logout/401 clearing, small screens/large font, keyboard open/close, Android file viewer and account switching. Recheck Stripe sandbox reconciliation; leave incentives disabled unless explicitly configured with capped budget.

Record device/OS, commit, server build, timestamp, expected/actual and request ID. Never attach private keys, tokens or real identity documents to logs.
