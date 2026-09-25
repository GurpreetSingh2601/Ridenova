# RideNova Build 22.1 Hotfix

Passenger **v0.22.1** + Driver **v0.5.1**.

## Fixes

1. **Driver false server error fixed**
   - Normal coroutine cancellation from stopping/restarting the ride-offer polling loop is no longer shown as `Server: StandaloneCoroutine was cancelled`.
   - Real backend/network errors are still surfaced.

2. **Passenger route ETA reliability improved**
   - The Google Routes request was simplified to a broadly supported traffic-aware request.
   - Removed the optional `SHORTER_DISTANCE` reference-route request that could make the complete route call fail for some development API configurations/regions.
   - Increased the route response timeout to 20 seconds.
   - If Google routing still cannot be reached, the emergency prototype fallback now uses a distance-sensitive speed assumption instead of a flat 32 km/h and remains explicitly marked `isApproximate=true`.
   - This fallback is not a replacement for Google live traffic; it only avoids obviously inflated prototype ETAs.

3. **Recent destinations compacted**
   - The destination-search screen now shows only the single most recent unique destination.
   - Additional history may remain stored internally for account sync/future history UI.

## Important routing check
For Google-like live ETAs, make sure the Google Cloud project used by `MAPS_API_KEY` has the **Routes API** enabled. If the Routes call is unavailable, RideNova will show an approximate estimate rather than a live-traffic ETA.

## Backend
No database reset is required. Continue using the same shared backend and existing database configuration.
