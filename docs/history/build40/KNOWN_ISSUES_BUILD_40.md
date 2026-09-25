# Build 40 known issues and limitations

Passenger 0.32.1 includes the long-route Confirm/413 and JSON-null warning fixes.
The 137-test backend suite and source preflight pass; rebuilt Android/device
acceptance is still outstanding. This correction does not complete Build 40 acceptance.

1. The Python/SQLite service is for local or trusted development networks only; do not expose it directly to the internet.
2. Android APK compilation was blocked by unavailable Gradle download in the packaging environment. Compile both apps on the configured Windows/Android machine.
3. Google keys remain build configuration and need correct package + signing SHA-1 restrictions for each app.
4. Client-selected routes are validated and quote-bound, but production routing should be requested by the secure backend.
5. Development OTP is shown in-app; no SMS is sent. Payment/payout records move no money.
6. Background location depends on Android permissions, foreground-service policy and OEM battery settings; device acceptance is mandatory.
7. SQLite is not the planned multi-instance Render staging database. Build 41 must introduce PostgreSQL and versioned migrations.
8. Historic internal modules (`fleet28.py` through `fleet35.py`) represent additive compatibility lineage, not separate backends.
