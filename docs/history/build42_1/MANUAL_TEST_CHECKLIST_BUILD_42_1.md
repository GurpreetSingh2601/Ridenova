# Build 42.1 — one acceptance checklist

Use your existing staging accounts and a test ride. Update both apps with the same staging package and signing key; keep Render/database configuration intact.

## Passenger

- [ ] Welcome, phone, invitation-code and profile screens use the RideNova logo consistently. Existing account/profile survives an app update.
- [ ] Open/close the keyboard repeatedly, go Back, rotate and use larger system text. Fields, text and primary action remain reachable without a blank/cropped area.
- [ ] Home, search, saved places and ride selection remain usable. Pan/recenter the map and select a road route.
- [ ] Quote/confirm shows the same selected route and one clear GST-inclusive total. Missing payment and network failures show an actionable message; repeated taps do not book twice.
- [ ] Complete Stripe test checkout, return and Verify. Confirm a saved test card appears; cancelling checkout must not claim it was added.
- [ ] Follow one real staging test ride through matching, assignment, arrival, PIN/start and completion. Reopen during the ride to confirm recovery.
- [ ] Rate the completed trip and try a support message. Failed submission keeps the dialog/error; retry remains possible.
- [ ] Trip filters, receipt, payment authorization message, profile, saved places and light/dark/system themes work. `Authorized · awaiting capture` does not imply captured funds.

## Driver

- [ ] Sign-in shows the **Driver app icon**, readable fields and no jump/crop when the keyboard closes. Existing login still works. Development-only signup/recovery remains usable in development; staging is invited sign-in only.
- [ ] Home, Earnings, Trips and Account bottom tabs work when idle. Menu, alerts/shortcut, document review progress, account actions and sign-out remain reachable.
- [ ] Receive an exclusive offer and, with two eligible nearby drivers, a Trip Radar offer. Map, earnings, route, timer and fixed action buttons remain readable. Test a small screen, landscape and 150% text; scrolling may be necessary for details.
- [ ] Accept with two drivers; only one succeeds. Decline an offer and confirm it does not repeatedly return unchanged. Accept/expire errors stay understandable.
- [ ] Complete a trip, review earnings, open a trip from earnings/history, search by address and use Back. Back returns to the trip list; switching through the menu restores bottom navigation.
- [ ] Background/reopen during a trip, reconnect after a network interruption and confirm GPS/state recovery without a second assignment. Test permissions on your Pixel/OEM device.

## Admin and integration

- [ ] Hard-refresh `/admin`, sign in as your existing Owner and visit every workspace. The revision reads Build 42.1 / Admin 0.9.1.
- [ ] Use Refresh in each workspace; time updates. Disconnect the network and retry: existing data remains with a refresh error. Reconnect and retry successfully.
- [ ] Check your restricted roles against `STAFF_PERMISSIONS_AND_TESTING.md`. Forbidden workspaces/actions must remain unavailable and backend requests must still be rejected.
- [ ] Open a ride's timeline, review documents, inspect support/feedback, create/disable a temporary staff account and inspect its audit trail.
- [ ] Check test Finance with a completed ride: human-readable status, balances, capture/refund/reconciliation and existing zone controls. Do not use live payment keys.
- [ ] Sign out while a refresh is running. Records disappear and do not return. Test session expiry. Repeat at a mobile browser width.
- [ ] Confirm Passenger, Driver and Admin show the same test ride and that earlier accounts/trips remain in the existing database.

Record any failed item with the screen, app version, device/text size, exact steps and whether the backend request failed. Do not send secret keys, passwords or full card details with screenshots.
