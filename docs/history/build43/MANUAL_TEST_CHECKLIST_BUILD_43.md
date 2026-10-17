# Build 43 — one device acceptance pass

Use two invited test accounts/devices and the existing Owner account. Run against your configured staging API; no real cards or passengers.

- [ ] Confirm build/version in both apps and Admin; existing accounts/trips survive the update.
- [ ] Passenger: choose a pickup by search, then map tap and map movement. Confirm it differs from GPS. Return Home and wait for GPS; selected pickup must not move.
- [ ] Change pickup from fare confirmation. Verify route selection opens, distance/time/fare refresh, and the booked ride uses the reviewed quote. Test Economy/Comfort/XL where eligible.
- [ ] Deny location, turn GPS off and use an approximate fix. Manual selection remains reachable; no silent sample location is booked. Check portrait, keyboard open/closed, large text and light/dark themes.
- [ ] Add pickup instructions; finish booking. Driver sees the same notes and street address. Admin ride details show text safely, including punctuation.
- [ ] Before booking, close/reopen Passenger. Continue booking restores destination/pickup/notes; route and fare refresh. Sign out: the next account must not inherit the draft.
- [ ] Complete a normal ride. Driver sees empty stars immediately; select and submit. Reopen details: saved rating remains. Skip never submits a rating; history still permits feedback.
- [ ] Driver arrives near pickup with fresh GPS. Timer counts five minutes; restart Driver midway without resetting the server timer. Passenger shows arrival/waiting information.
- [ ] Before five minutes, no-show is disabled. After five minutes, stale GPS or leaving the area prevents cancellation. Return with fresh GPS, check the confirmation and submit a reason.
- [ ] Passenger/Admin show no-show, zero fee, no earnings; Driver becomes available. Passenger can book again. Check Admin status filter and existing support access.
- [ ] Retry after a lost response. One booking, one assignment and one final transition remain. A normal Start trip during waiting still works with the correct PIN.
- [ ] Test background/foreground and network reconnection on both phones; confirm no stale active trip or duplicate assignment.
- [ ] Admin: refresh each workspace, test restricted roles and logout/session expiry. Existing Stripe test setup/authorization and Finance still work with your test keys.

Record device/Android version, app version, action, expected/actual result and API timestamp for failures. Do not include secrets, full card details or live personal data in shared logs.
