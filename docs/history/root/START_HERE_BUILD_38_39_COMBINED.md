# RideNova Builds 38 + 39 — combined development release

**Source baseline:** the user-tested Build 36 source **with the Build 38 Passenger matching-recovery hotfix retained**. This is the combined milestone requested after the Passenger bug was confirmed fixed. Passenger version `0.31.1-build38-39`; Driver version `0.16.1-build38-39`. Existing Admin Portal 2.0 is extended; shared backend remains a single Python/SQLite development service.

## Implemented in this package

- **Passenger:** preserves the tested missing-active-ride loading/recovery hotfix, existing idempotent booking and all existing trip and map workflows. No new booking protocol or duplicate-booking pathway introduced.
- **Admin staff foundation:** separate staff usernames/passwords; salted PBKDF2 password hashes; random bearer sessions (only SHA-256 hashes stored), 8-hour session expiration, explicit logout and disabled-account session revocation. Staff roles: OWNER, OPERATIONS, SUPPORT, FINANCE, COMPLIANCE. Permissions are checked on the shared backend's `/v1/admin/` and `/v2/fleet/admin/` endpoints, not merely via the UI.
- **Staff portal:** staff sign-in, staff directory, creation of other staff accounts (owner only), enable/disable accounts, role-aware sidebar, audit display. No passwords/tokens are embedded in the ZIP or returned in the staff listing.
- **Operational tools:** server-side rides pagination (25 rows by default), status and ride-ID search, interactive ride-detail and event timeline panel. Previous dashboard and driver/document review sections remain.
- **Audit:** staff sign-in/sign-out, account creation/disable/enable, and admin mutation attempts and successful results are recorded. Development audit is capped to the newest 100 items per view; it is not a production immutable audit archive.
- **Role-limited data:** finance ledger/totals are withheld from roles without finance permission; driver roster data is withheld from roles without fleet permission. Other privileged endpoints enforce permissions independently.
- **Driver:** earnings period selector (Today / This week / All time), estimated earnings, trip count, average earnings, compact five-trip earnings summary, near-expiring document reminders, and version labels. Existing sound, navigation, Trip Radar, GPS, dispatch and PIN features remain unchanged.

## IMPORTANT: development-only access, not production identity verification

The backend is intentionally loopback-only by default and must **not** be exposed publicly. Staff accounts prove possession of credentials in the development environment; they do NOT verify a staff member's real-world identity. MFA, login throttling, password-reset/identity-proofing, encrypted document storage, TLS termination, production auditing, privacy retention and hardened production deployment remain outstanding.

### Back up your existing database first

Stop the backend, then back up your actual SQLite database (and any `-wal`/`-shm` files if present). If you have custom MySQL code, do **not** blindly replace it with this packaged SQLite development backend: reconcile the schema and implementation first. The added `admin_staff`, `admin_sessions`, `admin_audit` tables are `CREATE TABLE IF NOT EXISTS` migrations; existing rides, driver profiles and earnings are not deleted or reset.

### First-time staff owner setup (Windows PowerShell)

From the extracted `Passenger` directory, in a NEW terminal:

```powershell
$env:RIDENOVA_OWNER_USERNAME = "owner"
$env:RIDENOVA_OWNER_PASSWORD = Read-Host "Enter a NEW unique password (14+ characters)"
python backend/server.py --database ridenova-dev.sqlite3
```

**Use the same `--database` path as your previous running backend.** The above filename is only the original development default; don't accidentally start a blank database in a different working directory. A one-time owner account is created only if the staff table is empty. Subsequent restarts should use the same database. Remove temporary password environment variables from the shell after setup (`Remove-Item Env:RIDENOVA_OWNER_PASSWORD`), and never put secrets into Git or project ZIPs.

**Important migration behavior:** before any staff accounts exist, the older `RIDENOVA_DEV_ADMIN_TOKEN` remains available for legacy local-development verification. **As soon as an owner account exists, the old shared admin token is rejected.** You must sign in at `/admin` using the owner account. Existing Driver and Passenger credentials remain separate and unchanged.

Open `http://127.0.0.1:8080/admin`. Sign in, open **Staff & access** from the left sidebar, and create a least-privilege account for your coworker. Do not share the owner's credentials. Password delivery to staff should happen separately through a secure channel. Set staff roles intentionally: an Operations user can handle rides/driver workflows; Support handles cases; Finance sees finances without fleet controls; Compliance reviews documents. Sensitive actions are always checked by the backend.

### Test commands

Stop the running backend, open a terminal in the extracted `Passenger` directory:

```powershell
python -m unittest discover -s backend -p "test_*.py"
```

Existing and new backend tests: **121 passed in the build environment** (Linux, Python). `node --check` passes for concatenated Admin JavaScript. Android Gradle compilation could NOT be completed in the build environment: wrapper download of Gradle 9.6 failed due to unavailable `services.gradle.org`. Browser interaction tests and Windows/phone testing remain your acceptance gates. Python's existing legacy test suite still emits some connection ResourceWarnings even when tests pass; this is not a confirmation of Windows behavior.

### Device and admin acceptance checklist

1. Open Passenger, book Ride Now and confirm it goes to matching. If a local ride is briefly missing, it must restore the same backend booking—no temporary `No active ride`, no duplicate ride.
2. Driver receives offer, accepts, enters PIN, and completes the trip. Existing 20-second offer/Trip Radar handling, sound, GPS and navigation should be unaffected.
3. Start backend against your backed-up original database. Visit `/admin`, sign in with owner, verify existing rides and document records are still present.
4. Open **Rides**, test pages 1, 2 and 3 with more than 50 rides, status filters, ride-ID search, and timeline detail panel. The table fetches 25 rows at a time rather than loading the full history.
5. Create a Support staff account, sign in in a private tab: support actions work, but driver-admin operations, staff management and finance are blocked. Test Finance and Operations separately.
6. Disable a staff account: its existing token is invalidated and it can no longer sign in. Verify the owner cannot disable their own last-owner account.
7. On Driver, check Earnings period filters and document reminders. Confirm all financial data remains clearly labeled as development estimates, NOT actual payouts.

## Scope limits / remaining work

This milestone is a **development integration release**, not a launch candidate. The Admin UI is designed for role-controlled operation, but MFA, production hosting and identity verification are not included. Server pagination covers rides; support/feedback and other large datasets still need paginated APIs. Finance transactions and payouts remain development-only. Driver UI refinements are targeted (earnings and document alerts), not a wholesale interface redesign. Preserve this distinction when testing or planning the next build.
