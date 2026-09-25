# Build 31 Android acceptance checklist — not yet executed

First run VERIFY_ANDROID.ps1. Use your existing database, one server and Maps configuration. Keep a backup of Build 30 and your database.

Test both portrait and landscape on the Pixel; also check a narrow emulator, large font (150–200%), gesture navigation and the keyboard open.

## Driver

- Sign in; create/recover an account; inspect keyboard scroll and error messages. Sign out and switch accounts; ensure no previous driver's trips remain on the phone.
- Home offline: map and Go online are visible and reachable. Online: one Go offline action, metrics, and clear waiting state. Disable location/connection and inspect messages.
- Empty Trips: explanatory card and Home action. Completed trips: newest first and readable addresses/earnings. Empty/nonempty Earnings.
- Book a Passenger trip while Driver is on each tab. Incoming request must show pins, both road legs (blue approach, green trip), full route framing and expiry. Scroll details: countdown and Accept/Decline must remain available.
- Try no Maps key, disabled Routes API, denied key restrictions, no network and Retry. No invented straight road lines; accepting does not wait for the map. Let an offer expire and confirm Accept is disabled.
- Accept: return to Home controls. Check Arrived, incorrect/correct PIN, Start, Complete and Done. Open keyboard: PIN and Start stay reachable. Cancel before pickup; no cancel action after Start.
- Open navigation: map remains visible; pan, Follow GPS, Google Maps, Return to trip and Android Back. Stop server, resume/restart during trip; verify feedback and recovered controls.
- Account: Documents opens real workflow, not preview. Upload all four types, view review/expiry status, refresh, reject/reupload. Android Back returns to Account.

## Passenger

- Welcome and phone/OTP/profile forms with large font and keyboard; no clipped Continue controls.
- Home map retains visible space with active ride, saved places and recent destination.
- Type quickly in search, clear query while request is pending, enter no-match query, select long result. Old results must not replace newer results.
- Ride selection: drag sheet, switch route/category, Schedule and Choose remain usable. Review fare/GST and long payment label; confirm action remains accessible.
- Complete a ride with Driver. Check matching, arrival PIN, live progress, cancellation policy, Trips and receipt. Account, saved places, payment selection, appearance and language preview retain prior behavior.

## Data and setup

- Both apps, Driver accounts and Admin still use the same backend/database. /health remains API 30.0 (UI build version is 31).
- Confirm documents/history survive restart, sign-out and sign-in. Test simultaneous drivers with two installations, or sequential accounts on one phone.
