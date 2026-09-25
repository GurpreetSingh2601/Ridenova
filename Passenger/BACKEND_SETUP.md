# Passenger backend setup — Build 41

Passenger, Driver and Admin use the same server in this project's `backend/` directory. Start it from the repository root using `START_SERVER.py`; do not create a Passenger-only or Driver-only server.

Set `RIDENOVA_API_BASE_URL` in `Passenger/gradle.properties`, for example:

```properties
RIDENOVA_API_BASE_URL=http://127.0.0.1:8080
```

For a USB device, run `adb reverse tcp:8080 tcp:8080`. For an emulator use the appropriate host bridge address. Never put credentials in the URL or commit secrets. Full startup, database-copy migration and verification instructions are in `../START_HERE_BUILD_41.md`.

Those commands apply to local debug builds. For the isolated staging variant,
set `RIDENOVA_STAGING_API_BASE_URL` in both projects and run `assembleStaging`
after authorized deployment. It uses HTTPS without ADB reverse. See the root
`DEPLOYMENT_AND_MIGRATION_BUILD_41.md` for PostgreSQL and hosted setup.
