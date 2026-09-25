# Build 34 device acceptance

Use two Android installations/devices when testing Passenger and Driver simultaneously.

## Upgrade

- Start only the Build 34 server using the existing database.
- Confirm `/health` shows `34.0` / build `34`.
- Confirm previous accounts, documents, trips and login credentials remain present.

## Passenger

- Complete a shared-backend test ride.
- Open the completed ride in Trips and confirm the receipt/map still render.
- Submit a five-star rating with two tags and a comment.
- Reopen the trip and confirm the saved rating loads; edit it and confirm it updates.
- Open Get help, focus the description, show/hide the keyboard and confirm no blank or hidden lower screen.
- Submit a trip-linked support case and confirm the displayed case count increases.

## Driver

- Confirm login/sign-up and keyboard behavior remain correct from Build 33.
- Complete a ride, rate the rider on the completion card, then press Done.
- Open Trips and confirm Rate rider and Support are available on the completed trip.
- Submit a support case while the keyboard is open and confirm success is shown.

## Admin

- Open `/admin`, enter the Admin token and load the dashboard.
- Confirm rating count/average and the submitted feedback rows.
- Confirm support cases show the correct role, category and ride ID.
- Move a case to In review with a note, refresh, then resolve it.
- Confirm unauthenticated Admin API calls still return 403.

## Regression

- Verify online/offline, GPS, offer countdown, accept/decline, arrival, PIN start and completion.
- Verify scheduled rides, cancellation, earnings history, documents and account switching.
- Verify map pan/zoom and recenter behavior in both apps.
