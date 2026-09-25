# RideNova v0.21 — Account Sync and Payment Foundation

This combined release completes the planned v0.20 and v0.21 passenger milestones. It preserves v0.19 authentication, scheduled rides, server fares/GST and trip persistence.

## Included

- Home, Work and up to eight recent destinations sync with the authenticated account.
- Payment Methods lists, adds, selects and removes development card references.
- New accounts receive a default Visa ending in 4242.
- The backend never accepts or stores a real card number or CVV.
- Every ride snapshots its payment reference and payment status.
- Completed rides record `CAPTURED_DEMO`; free cancellations and expired schedules record `VOIDED`. No real charge occurs.
- Confirmation and trip details show payment information.
- The welcome screen explains that phone verification handles sign-up and returning sign-in.
- Pickup labels use PST/PDT-style abbreviations instead of a bare numeric offset.

Android version: **0.21.0** (`versionCode 22`). Backend health version: **0.21.0**.

## Upgrade without losing v0.19 data

1. Keep the v0.19 project and database as a backup.
2. Extract this ZIP and open the folder containing `settings.gradle.kts`.
3. Copy your private `local.properties` from v0.19 into this project.
4. Keep this in the project-level `gradle.properties` for a physical Pixel:

```properties
RIDENOVA_API_BASE_URL=http://127.0.0.1:8080
```

5. Stop v0.19. Start v0.21 against the exact same SQLite file:

```powershell
$env:RIDENOVA_DEV_ADMIN_TOKEN="choose-a-local-development-token"
python backend/server.py --database "G:\your-v0.19-folder\ridenova-dev.sqlite3"
```

The schema upgrade is additive. Accounts, profiles, quotes and trips remain. New account-data and payment tables are created automatically. Back up the database first. If `--database` is omitted, Python uses or creates `ridenova-dev.sqlite3` in the terminal's current folder.

6. For a physical Pixel, confirm or recreate the reverse tunnel:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -s YOUR_PHONE_ID reverse tcp:8080 tcp:8080
```

7. Sync Gradle, Clean Project, Rebuild Project and Run. For the standard emulator use `http://10.0.2.2:8080`; no reverse command is required.

## Test walkthrough

1. Sign in with the same phone number and displayed development OTP `246810`.
2. Set Home and Work, and search several destinations.
3. Open Account → Payment methods. Confirm the default card, add another development reference and make it default.
4. Get a backend fare. Confirm subtotal, GST, total and payment method appear before booking.
5. Book and complete a ride with the development admin simulator.
6. Confirm trip details show **Development payment recorded**.
7. Sign out and back in. Profile, trips, Home, Work, recent destinations and payment methods should return.

## Current limits

This is not payment processing. There is no provider SDK, card scanning, wallet tokenization, authorization hold, refund, chargeback, receipt ledger or PCI production workflow. Brands and last-four values are non-sensitive test labels. Driver dispatch remains simulated.

Next: **v0.22 — Driver Android app, driver/dispatch backend and basic internal admin console**.
