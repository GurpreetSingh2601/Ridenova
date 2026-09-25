# Build 31.1 changes

## Functionality first

- Replaced Admin's misleading legacy-driver status display with registered fleet status. Overview and Fleet refresh use the same renderer and update each other. Active trip status and assigned driver ID are shown together.
- Added dispatchReady/dispatchReason to fleet status: online intent, GPS freshness, documents, approval and active trip are distinguishable. Existing dispatch eligibility rules are unchanged.
- Driver continuously reconciles server state, including after initial connection failure, and restarts offer polling if it has stopped.
- Renewed/replaced offers update the request screen's ID/deadline. Offers received during an in-flight action are reconsidered after it completes. Completing a trip no longer prevents a following offer from appearing until Done is tapped.
- Background location service now polls offers and sends expiring, high-importance request notifications. Foreground and background polling share the existing server-side offer lease. Logout/offline/token revocation clear alerts and stop tracking.
- Slow GPS publishes are allowed to finish instead of being cancelled on every new location callback.
- Old servers lacking login/logout endpoints now produce a clear upgrade message. Active-trip logout has an explanation; server enforcement remains authoritative.
- Location and notification permission prompts are sequenced. Returning from Android settings refreshes location permission state.

## Driver UI

- Map fills the home canvas; measured map padding keeps route controls and Google attribution above the dock.
- Top-left drawer replaces bottom tabs, centred earnings opens Earnings, and the bell opens alert settings.
- A compact status card sits above a fixed bottom availability button. System status/navigation bar icon appearance follows the theme.
- Requests have a larger map area, prominent fare, route preview and fixed expiry/actions.
- Optional draggable floating shortcut, with explicit Display over other apps permission; tap to open Driver. Hides on lock screen, foreground, offline and logout.

Passenger UI and prior features are retained. No separate backend, destructive migration, category relaxation, automatic acceptance or new real-payment behavior was introduced.

## Platform references consulted

- Android notifications: https://developer.android.com/develop/ui/compose/notifications/create-notification
- Foreground-service start restrictions: https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
- Application overlays: https://developer.android.com/reference/android/view/WindowManager.LayoutParams#TYPE_APPLICATION_OVERLAY

Implementation review is not a claim of Android runtime acceptance. See VERIFICATION.md.
