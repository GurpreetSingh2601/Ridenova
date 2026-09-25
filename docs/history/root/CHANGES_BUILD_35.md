# RideNova Build 35 — Radar, Eligibility and Trip Detail

## Release versions

- Passenger: `0.31.0-build35` (`versionCode 39`)
- Driver: `0.16.0-build35` (`versionCode 36`)
- Backend health version: `35.0`

## Major additions

### Driver eligibility controlled by operations

- New driver accounts no longer self-assign Economy, Comfort or XL.
- Every new account starts with Economy eligibility.
- Admin **Ride types** control can add Comfort and/or XL after vehicle,
  capacity, documents and service-quality review.
- Existing driver category assignments are migrated, not discarded.
- Dispatch checks the authoritative multi-category eligibility table.

### Trip Radar

- A request within 4 km of at least two eligible account drivers opens a
  shared 12-second Radar offer.
- All candidates see the same request and nearby-driver count.
- The first valid claim is protected by a SQLite transaction; one ride cannot
  be won by two drivers.
- If nobody claims it, it automatically changes to the normal exclusive
  20-second request flow.
- Token-only legacy test drivers retain the prior exclusive behavior.

### Driver experience

- Rebuilt login/sign-up scrolling behavior so closing the keyboard restores
  the complete screen instead of leaving an empty viewport.
- Removed ride-category self-selection from sign-up and explains admin review.
- Compact offer sheet fits earnings, pickup, destination, time, distance and
  estimated gross/hour above the pinned action row on normal phone screens.
- Radar offers use a clear **Match ride** action and shared-offer banner.
- Completed trips are tappable and open a route map plus pickup, destination,
  ride type, time, distance, fare and earnings.
- Floating shortcut uses the actual RideNova Driver artwork instead of `N`.
- Foreground and request notifications use a transparent monochrome version
  of the same Driver mark, as required by Android notification rendering.

### Passenger experience

- Immediately after completion, a bottom sheet asks for the driver rating.
- The same sheet exposes Safety / trip support without requiring Past Rides.
- Build 34's missing `snapshotFlow` import is included.

### Address and route accuracy

- Generic pickup labels such as **Current location** are replaced with the
  captured street address in Driver history and Admin Trips.
- The backend stores route points with the quote. With Google Routes configured
  this is the road polyline; the development fallback stores pickup/drop-off
  geometry.

## Verification

- Backend: **115 tests passed**.
- Python modules compile successfully.
- Admin inline JavaScript passes syntax validation.
- Android Gradle compile was attempted, but this workspace cannot download the
  Gradle 9.6 distribution because outbound Gradle network access is blocked.
  The included projects are intended to sync/build normally in Android Studio.

