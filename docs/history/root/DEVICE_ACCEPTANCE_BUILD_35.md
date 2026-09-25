# Build 35 device acceptance checklist

## Driver authentication / keyboard

- Open Sign in, focus identifier and password, then close the keyboard.
- Confirm the header and full form return; no mostly blank viewport remains.
- Repeat on Create account from its top, middle and licence-plate fields.
- Rotate the device and repeat once if rotation is supported.

## Eligibility

- Confirm Create account has no Economy/Comfort/XL self-selection.
- Confirm the account starts Economy-only.
- Grant Comfort/XL with Admin **Ride types** and verify Driver status updates.

## Trip Radar and exclusive fallback

- With two eligible drivers within 4 km, confirm both see one Radar request.
- Accept concurrently; confirm exactly one driver is assigned.
- On a second request, let 12 seconds expire and confirm one driver gets a
  normal exclusive 20-second offer.
- With only one nearby eligible driver, confirm Radar is not used.

## Request layout

- On the smallest supported phone, verify earnings, pickup, destination,
  total time, distance, gross/hour and action buttons are visible.
- Verify no action button requires scrolling.

## Completion and history

- Complete a ride; Passenger must show rating stars and Safety / trip support.
- Submit a rating and confirm it appears in Admin feedback.
- Driver Trips: tap the trip and verify map, addresses, route, fare and earnings.
- Admin Trips and Driver Trips must show a street pickup address instead of
  `Current location` when an address was captured.

## Branding

- Enable Driver floating shortcut and confirm the Driver logo replaces `N`.
- Confirm incoming-request and foreground-service notifications show the
  monochrome Driver logo silhouette.

