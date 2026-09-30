# RideNova Driver 0.19.0 — Build 42

The Driver Android app connects to the same shared backend as Passenger and Admin. It supports account access/onboarding, server-controlled ride categories, online/presence state, Trip Radar and exclusive offers, atomic acceptance, pickup/arrival/PIN/start/complete lifecycle, active-trip recovery, history, ratings, support and development earnings.

Configure `RIDENOVA_DEV_URL` and `MAPS_API_KEY` in `Driver/local.properties`. Setup and verification are in the repository-root `START_HERE_BUILD_41.md`.

For controlled staging, set `RIDENOVA_STAGING_API_BASE_URL` in gradle.properties
and build the staging variant after deployment. It uses an isolated package and
real backend/location code even though the APK is not debuggable. No staging API
or reusable Driver bearer credential is bundled.

This is a development build. Identity/document approval, payments and payouts are not production integrations, and real-world passenger service is not authorized by this source package.

Build 42 keeps the existing driver workflow; capped boost awards are recorded server-side and driver-facing boost display is planned for Build 43.
