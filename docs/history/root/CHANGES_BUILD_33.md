# RideNova Build 33 — Driver Access & Operations

## Versions

- Passenger: **v0.29.0-build33** (`versionCode 37`)
- Driver: **v0.14.0-build33** (`versionCode 34`)
- Shared development backend: **33.0**
- Admin portal: **v0.4.0**

## Driver authentication and keyboard fix

- Replaced the bare authentication `Column` with an opaque themed full-screen surface and keyboard-safe scaffold.
- Added safe drawing insets, `adjustResize`, IME bottom padding, a scrollable form and persistent form values. The keyboard can no longer expose the activity's white window behind the form or leave half of the screen blank.
- Added explicit light/dark window and navigation-bar backgrounds.
- Added show/hide buttons for password fields, correct phone/password keyboard types, Next/Done actions, clearer validation, progress feedback and readable inline errors.
- Redesigned Sign in, Create account and Recover access into a consistent RideNova Driver entry experience.

## Driver accounts and security

- New driver accounts can include a normalized Canadian phone number.
- Drivers can sign in with either username or phone number. Existing username-only Build 30–32 accounts continue to work.
- Phone numbers are unique and only masked values are returned to the app and Admin status data.
- Added password change from **Account → Sign-in & logout / Account & security**, requiring the current password.
- Added a server-backed account overview with document readiness, completed-trip count and lifetime estimated earnings.
- Existing drivers who have not configured sign-in details can now add username, phone and password from their retained profile.
- Login rate limiting applies separately to normalized username/phone identifiers, and registration uniqueness remains transactional.

## Shared backend and Admin

- Added an additive `phone` migration to `fleet_logins`; current databases and driver records are preserved.
- Added `GET /v2/fleet/driver/account-overview` and `POST /v2/fleet/driver/password`.
- Build 33 health response identifies backend `33.0`.
- Admin v0.4.0 shows the Build 33 identity and masked driver phone information without exposing the complete number.

## Preserved from Build 32

Dispatch matching, approval/documents, offer leases, background GPS, request notifications and sound, floating shortcut, in-app navigation, live passenger tracking, map gesture ownership, scheduling, pricing, payment simulations and the existing SQLite data remain in place.

This remains a local development system. Phone ownership is not verified, identity checks are not performed, and there are no real payments or payouts.
