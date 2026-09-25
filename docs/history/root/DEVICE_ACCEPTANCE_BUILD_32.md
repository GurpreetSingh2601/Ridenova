# Build 32 device acceptance

Use a physical Android phone for this test. The Pixel 10 Pro is appropriate.

## Driver map gesture test

1. Open Driver Home while offline or online with no request.
2. Drag the map left and right repeatedly, including starting near the left edge.
3. Pinch to zoom, rotate, and pan diagonally.
4. Confirm the side menu never opens from a map gesture. It should open only from the menu button.
5. After panning away, wait for one or more GPS updates. Confirm the map stays where you left it.
6. Tap the recenter button. Confirm RideNova smoothly recenters.

## Navigation follow test

1. Start a test ride and open RideNova in-app navigation.
2. With Follow GPS active, confirm the camera follows reported location updates.
3. Pan the map manually. Confirm following stops immediately.
4. Tap Follow GPS and confirm following resumes.

## Passenger map test

1. Book/assign a development ride.
2. On the live trip map, pan/zoom manually.
3. Confirm driver GPS refreshes do not yank the camera away from the rider's chosen view.
4. Confirm the driver marker itself moves smoothly when a new location fix arrives.

## Ride selection sheet

1. Open ride selection.
2. Repeatedly drag the bottom sheet between partially expanded and expanded states.
3. Watch the route map while dragging. Compare for stutter against Build 31.1.

## Regression

Verify login, online/offline, offer alert sound, 20-second request, accept/decline, arrival, PIN, trip start/completion, trip history, earnings, Account, Driver onboarding, and Admin portal.
