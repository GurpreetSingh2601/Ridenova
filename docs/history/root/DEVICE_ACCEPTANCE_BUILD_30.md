# Build 30 device acceptance checklist

These checks require your Maps credentials and test phones; they are not a claim of completed device testing.

- Install both apps; Maps loads using your keys. Confirm Build 30 in the app version settings.
- Register two different driver profiles on separate installs. Driver A's credential must not restore Driver B's history.
- Upload each allowed file type. Reject one document, read its reason in Android, replace it, re-review it, then approve the driver.
- Attempt online before approval: clear error, no dispatch. After approval, go online and receive a fresh GPS fix.
- Place both drivers in the same category at distinct locations; book a Passenger ride. Only the nearest eligible driver should receive it.
- Let an offer expire while the original phone is backgrounded/disconnected; the other driver should receive the reassigned request.
- Accept, arrive, try a wrong PIN, enter the correct PIN, start, complete. Confirm driver history, passenger history and Admin earnings.
- Keep a driver stationary for more than one minute: passenger availability should remain available while location updates are running.
- Background Driver while using external navigation: verify foreground-location notification and passenger map updates. Test on your actual Android version and battery settings.
- Restart Driver and the backend during an active ride; recover the same ride and continue.
- Cancel as driver before pickup; confirm reassignment and a new Passenger PIN. Cancel as Passenger and confirm offer/active-trip clearing.
- Suspend an idle driver in Admin; Android should become offline and stop showing new requests. Suspend an assigned driver; allow that trip to finish, then require reapproval before more work.
- Edit profile and confirm Admin sees the changes and documents need review again.
- Test network loss at acceptance and completion, reconnect, and verify one assignment and one earnings record.
- Reset a lost driver's access when idle, use Recover access with a new password, and confirm the old password and credential fail.
- Verify all previously used Passenger flows: saved places, recents, login, cards, scheduling, routing, fare breakdown and cancellation.

## New Build 30 account checks

- Upgrade an existing Build 29 installation without clearing storage. Set username/password under Account → Sign-in & logout; verify the same driver ID, documents, approval and history.
- Log out while idle. Verify the admin shows offline, GPS foreground notification stops, and the entry screen appears.
- Sign in as a second driver. Check that name, documents, active trip and earnings belong only to that second account. Then switch back without using Android Clear storage.
- Try logout at assigned, arrived and started stages. Confirm a clear error and that the active trip remains intact.
- Simulate network loss during logout; session must remain available with an error. Reconnect and retry.
- Sign in to the same account on another device; the old session must stop accepting commands, and an active ride must be restored on the new device.
- Rotate the screen and restart the app at entry, after sign-in and during an active ride.
- Try wrong passwords five times; verify the one-minute lock and successful retry later.
- Use Admin reset and Recover access, then verify the recovery credential cannot be reused.
