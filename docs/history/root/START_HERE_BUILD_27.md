# RideNova Build 27 — Driver major request and active-trip interface

## Versions
Passenger v0.24 unchanged; Driver v0.9.0; Admin v0.1 unchanged; shared backend Build 27.

## Changes
- **20-second request expiry is server-owned**, not restarted by polling. Updated the corresponding expiry boundary test. An offer reappears only after the existing 20-second cooldown, if the ride remains unassigned.
- Incoming offers display on a dedicated request screen rather than over the ordinary home-map chrome. The bottom navigation remains hidden.
- Clear earnings, category, pickup ETA/distance, destination, trip ETA/distance, estimated total trip time/distance, and illustrative gross-per-hour equivalent. Gross-per-hour is not net pay, a wage, or a guarantee.
- Countdown indicator uses the actual 20-second backend offer interval. Accept and Decline become disabled after expiry. Existing Nova request sound remains.
- During active trips the large online banner and multi-stat earnings strip are suppressed in favour of a compact ride/earnings header.
- Existing Account informational sections, navigation beta, GPS service, Passenger recent destinations, Admin dashboard and SQLite ledger are retained. No documents/tax upload or payment execution has been added.

## Installation
Back up your SQLite data and backend directory. Replace backend code as a unit, keep your own keys and tokens, restart the shared backend, rebuild/reinstall Driver in Android Studio. Passenger v0.24 can remain installed if it is working. Do not delete or recreate the database. From Passenger project root with backend stopped run `python -m unittest discover -s backend -p "test_*.py"`.

## Verification limitations
Backend automated tests run in this environment; full Gradle compilation and physical-device checks may require your Android Studio. Test 20-second offer expiry on actual phones, the dedicated request screen, sound start/stop, accept/decline, and GPS progression. This is a development build; use established navigation for real driving.
