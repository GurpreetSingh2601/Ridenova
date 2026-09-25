# RideNova v0.9 — Google Maps, Places # RideNova v0.7 — Google Maps, Places & road routing setup road routing setup

RideNova v0.7 uses the existing Maps/Places integration and adds a development call to Google Routes API so the route follows roads instead of drawing a straight line.

## Existing key
Keep your existing `MAPS_API_KEY` in the root `local.properties` file:

```properties
MAPS_API_KEY=YOUR_REAL_GOOGLE_MAPS_API_KEY
```

## Enable Routes API
In the same Google Cloud project:

1. Open **APIs & Services -> Library**.
2. Search for **Routes API**.
3. Enable it.
4. Open the API key you already use for RideNova.
5. Under **API restrictions**, add **Routes API** alongside:
   - Maps SDK for Android
   - Places API (New)
6. Keep the Android application restriction for `com.ridenova.passenger` and your debug SHA-1.
7. Save and allow a few minutes for the change to propagate.

v0.7 sends the Android package and signing-certificate headers with the Routes request. If Google rejects direct mobile Routes calls for your key/configuration, RideNova automatically falls back to an approximate distance/time and does not draw a fake straight-line route.

## Production note
The production app should request routes through the RideNova backend rather than calling Routes API directly from the passenger app. That will centralize credentials, quotas, routing policy, fare calculation, auditability, and abuse controls.
