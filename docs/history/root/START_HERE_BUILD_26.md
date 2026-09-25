# RideNova Build 26 — Driver-first UI and onboarding preview

## Versions
- Passenger v0.24.0: expanded destination search now shows up to 5 unique recent destinations; home still shows only the latest.
- Driver v0.8.0: focused request card, 30-second server offer window, review countdown and progress bar, no bottom navigation while reviewing, less online-screen clutter, expanded Account sections.
- Admin v0.1 and shared SQLite backend extended from Build 25.1; database preserved.

## Offer behavior
Offer lifetime is 30 seconds from initial server offer, not reset by polling. An expired offer cannot be accepted. This is a development choice; multiple-driver dispatch and reassignment will require further work. The screen displays pickup distance/time, trip distance/time, and estimated development gross before costs. The 30-second progress bar is meaningful only for backend offers.

## Account sections
Profile/vehicle editing remains development-only. Documents, taxes, settings, safety/support and About are functional information dialogs. Android app settings opens the OS settings screen. **No document uploads, tax IDs, background verification, payments, or payout submissions are implemented**; never enter personal tax numbers in development builds.

## Setup
Open both Android projects in Android Studio. Retain your own existing API URL, auth tokens and Maps configuration. Do not replace your real SQLite database; back it up before updating server.py. Keep shared backend on the same server for both Android clients and Admin. Do not assume a MySQL migration has been implemented.

From the Passenger project root, with the development backend stopped, run:
`python -m unittest discover -s backend -p "test_*.py"`
Then restart the backend and rebuild/reinstall BOTH Android projects. An offer lasting 30 seconds requires restarting the upgraded backend (not merely rebuilding Driver). Test an offer countdown and expiry, recent destinations, profile edits, account dialogs and opening Android settings.

## Limitations
Android Gradle compilation and physical-device testing have not been performed here. Navigation is still beta; use Google Maps when driving. No production onboarding or payment verification. This build is NOT launch-ready.
