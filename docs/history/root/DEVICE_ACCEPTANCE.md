# Build 31.1 device acceptance — not yet executed here

Compile/lint both apps first with VERIFY_ANDROID.ps1. Stop the older server, reuse your database and verify /health = 31.1 and Admin = v0.3.1. Test data only.

1. Sign in as the existing driver. Go online, publish GPS, then load Admin. Main fleet status and Fleet table must show the same driver ID, availability and readiness. GPS older than 30 seconds must be flagged as non-dispatchable.
2. Book Economy for an Economy driver. Receive/accept in Driver from Home, Earnings, Account and background. An XL booking must not be sent to an Economy-only driver.
3. Let an offer expire; verify Accept disables and a renewed lease updates its countdown. Decline, cancel Passenger request, then book again. Complete a trip and verify another request can appear even before pressing Done.
4. Drive lifecycle: accept → arrive → wrong PIN → correct PIN/start → complete. Admin must show the fleet driver's active trip and assigned ID alongside TRIP_STARTED. Check Passenger progress/history.
5. Login/logout: configure existing-account login once; sign out/in; switch accounts on one phone. History/documents stay with their accounts. Active trip logout is disabled with explanation. Revoked-session cleanup works. Stop server during logout: app must show an error, retain access and allow retry.
6. UI: large map, top-left drawer, centred earnings, bottom availability action, recenter above dock, readable system status icons. Check portrait/landscape, narrow screen, long addresses and 150–200% font. Menu opens all earlier screens.
7. Background: allow notifications, go online, press Home/open another app, create a ride. Verify high-importance request notification (Android settings permitting), sound, deadline removal and tap-to-review. No automatic acceptance/forced launch. Foreground sound must not continue after request ends.
8. Floating shortcut: explicit toggle + overlay permission; deny then grant, drag, tap, disable. It must hide inside Driver, on lock screen and on offline/logout. Granting overlay must not be required for notification delivery.
9. Notification permission denied, channel muted and Do Not Disturb: UI remains usable; Android controls alerts. Check lock-screen public notification does not reveal route details.
10. Kill/force-stop/reopen, rotate during request, revoke token on another login, lose/recover ADB/server connection. Reopening restores server state; do not expect delivery after force-stop before reopening.
11. Recheck Passenger booking/scheduling/payments/history and Admin document review/search/CSV. Historical full acceptance checklist remains in DEVICE_ACCEPTANCE_BUILD_31.md.
