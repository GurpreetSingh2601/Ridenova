# Build 33 device acceptance

Record Pass/Fail on a physical Android phone for each item.

- Driver Sign in and Create account remain readable in both light and dark mode.
- Opening and closing the keyboard never reveals a white background or blank lower half.
- Every authentication field can be reached by scrolling while the keyboard is open.
- Password visibility toggles work; Next/Done keyboard actions do not hide required fields.
- Invalid values show an inline error without losing entered non-password fields.
- A new account can sign in by normalized Canadian phone number and by username.
- Duplicate phone and username values are rejected without creating a partial driver.
- Account & security shows only a masked phone.
- Password change rejects the wrong current password and accepts a valid replacement.
- Existing username-only account can still sign in.
- Admin shows Build 33 and only a masked phone.
- Driver onboarding, approval, online/offline, offers, GPS, trip PIN and completion still work.
- Passenger booking, live driver map, cancellation, scheduled rides and completed trip history still work.

Android compilation and these physical-device checks must be completed on the configured development computer/phone before treating the build as accepted.
