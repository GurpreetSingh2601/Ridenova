# Start here — Build 35

## 1. Start the backend

From `RN35/Passenger/backend`:

```bash
python server.py --host 0.0.0.0 --port 8080 --database ridenova.db
```

Before starting it, set a long local-only `RIDENOVA_DEV_ADMIN_TOKEN` environment
variable if you will use the Admin portal. Do not put that token in either app.

Check that it is running:

```text
http://127.0.0.1:8080/health
```

The response must include `"status":"ok"`, `"version":"35.0"` and
`"build":35`.

For a physical phone, use the computer's LAN address in both apps. For an
Android emulator, use `10.0.2.2`. With USB debugging, `adb reverse tcp:8080
tcp:8080` also permits `127.0.0.1:8080` from the phone.

## 2. Configure Passenger

In `RN35/Passenger/gradle.properties`:

```properties
RIDENOVA_API_BASE_URL=http://YOUR_COMPUTER_IP:8080
MAPS_API_KEY=YOUR_ANDROID_MAPS_KEY
```

## 3. Configure Driver

Create/update `RN35/Driver/local.properties`:

```properties
RIDENOVA_DEV_URL=http://YOUR_COMPUTER_IP:8080
MAPS_API_KEY=YOUR_ANDROID_MAPS_KEY
```

The same Maps key may be used only if its Android restrictions contain both
package/SHA-1 pairs: `com.ridenova.passenger` and `com.ridenova.driver`.

## 4. Test the new flow

1. Create two Driver accounts and complete admin document approval.
2. In Admin, use **Ride types** to grant the categories each vehicle supports.
3. Put both drivers online with fresh location near the passenger.
4. Request the matching category in Passenger.
5. Confirm both drivers receive a **Trip Radar** card.
6. Match on one phone; confirm the other phone loses the request.
7. Complete the ride and confirm the Passenger rating/safety sheet appears.
8. Open Driver **Trips**, tap the completed ride, and verify its map/details.
9. Confirm Admin Trips shows the street pickup address, not Current location.

## Important scope

This remains a local-development stack. Identity verification, production
payments/payouts, emergency-service integration, push notification delivery,
production hosting and regulatory vehicle rules still require production
providers and operational policy.
