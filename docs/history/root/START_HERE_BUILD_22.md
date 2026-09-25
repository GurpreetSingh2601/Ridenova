# RideNova Build 22

## Included versions
- Passenger Android: **v0.22**
- Driver Android: **v0.5**
- Shared development backend: **Build 22**

This build continues from the verified Passenger v0.21.3 + Driver v0.4.1 integration. It does **not** create a separate Driver backend. Both apps continue to use the same RideNova backend.

## Main additions
1. **Server-controlled driver offers**
   - A driver offer now has one stable 15-second expiry instead of getting a new expiry on every poll.
   - An expired offer cannot be accepted.
   - Expired offers are temporarily skipped before they can be offered again.

2. **Online driver presence before assignment**
   - While the Driver app is online and open, it sends its latest device position to the shared backend.
   - The backend uses a fresh driver position to estimate distance and ETA to pickup.
   - If no fresh position is available, the development fallback remains 0 km / 5 min.

3. **Improved Driver request card**
   - Real pickup distance/ETA from backend dispatch when location is available.
   - Visible offer countdown.
   - Accept/Decline disables after expiry.
   - Clearer Build 22 online/dispatch status.

4. **Improved Passenger live-ride messaging**
   - Searching now reflects matching to the connected Driver app rather than the old admin simulator wording.
   - Driver map/location copy now reflects live position updates from the Driver app.

5. **Dispatch metadata**
   - Accepted rides now record development dispatch metadata (`pickupDistanceKm`, `pickupEtaMinutes`, `assignedAtEpochMs`) in the ride payload.

## Verification completed
Backend command:

```bash
python -m unittest discover -s backend -p 'test_*.py'
```

Result during packaging: **46 tests passed**. The existing test suite emits Python `ResourceWarning` messages for some SQLite connections, but the tests complete successfully with `OK`.

## Development server setup
Keep using separate admin and driver development tokens. Example in PowerShell:

```powershell
$env:RIDENOVA_DEV_ADMIN_TOKEN="your-admin-token"
$env:RIDENOVA_DEV_DRIVER_TOKEN="your-driver-token"
python backend/server.py
```

In the Driver app's `local.properties`, keep the matching driver token and development server URL, for example:

```properties
RIDENOVA_DEV_URL=http://YOUR_COMPUTER_LAN_IP:8787
RIDENOVA_DEV_TOKEN=your-driver-token
MAPS_API_KEY=your_maps_key
```

Do not commit `local.properties` or real credentials.

## Important scope note
Background location/foreground-service tracking is intentionally **not** claimed in Build 22. Driver location publishing in this version continues while the Driver app is open/foregrounded. Background GPS and active-trip recovery hardening remain Build 23 priorities.
