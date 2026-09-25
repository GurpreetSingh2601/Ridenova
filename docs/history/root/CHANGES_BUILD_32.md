# RideNova Build 32 — Fluid UX

## Versions

- Passenger: **v0.28.0-build32**
- Driver: **v0.13.0-build32**
- Admin/backend: preserved from Build 31.1 / API 30.0

## Main objective

Build 32 is a performance and interaction-quality release. It preserves the working dispatch, fleet authentication, background GPS, ride alerts, request sound, navigation beta, onboarding, Admin portal, passenger booking flow, and shared backend while reducing gesture conflicts and unnecessary UI work.

## Driver map changes

- **Map swipes can no longer open the side drawer.** The navigation drawer is now button-only; horizontal map gestures belong to Google Maps.
- **Manual map movement pauses automatic camera control.** Once the driver pans/zooms/rotates the map, GPS and route refreshes no longer snap the camera back.
- The bottom-right recenter/full-route control explicitly returns camera control to RideNova.
- Driver GPS marker motion is interpolated instead of jumping directly between reported fixes.
- In navigation mode, a manual map gesture disables Follow GPS until the driver taps **Follow GPS** again.
- Map pan, zoom, rotate, and tilt gestures are explicitly enabled.
- Driver state flows are collected with lifecycle awareness so UI collection pauses when the screen is not active.

## Passenger smoothness changes

- Passenger map camera now respects user gestures. After a rider manually pans/zooms the map, live trip updates no longer immediately recenter it.
- The live driver marker is interpolated between reported GPS fixes.
- Recenter returns camera ownership to RideNova.
- Passenger navigation transitions are shorter and subtler to reduce the heavy sliding feeling between screens.
- Ride-selection bottom-sheet drag no longer reads the sheet pixel offset directly during composition. The previous implementation could recompose the large map/route subtree continuously while the sheet was moving. Build 32 uses a stable map inset and lets Material 3 own the drag animation.

## Preserved behavior

No dispatch rules, fleet approval rules, ride request lease duration, authentication semantics, pricing logic, payments behavior, database schema, or Admin controls were intentionally changed in this build.
