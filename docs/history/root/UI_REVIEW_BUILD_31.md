# Build 31 screen audit and changes

Source audit of Driver first, then Passenger. This is not a report of visual/device test passes.

## Driver

| Screen/state | Review and change |
|---|---|
| Offline/online home | Separate map and controls instead of overlapping cards. Clear online state, one primary availability button, today metrics and location/connection messages. Landscape uses two columns. |
| Incoming request | Added map with driver/pickup/drop-off pins and road geometry for both legs. Independent route loading/retry; no fake road line. All coordinates and returned geometry inform map fit. Fixed Accept/Decline bar, expiry countdown, busy/expired disabling; estimates remain scrollable. |
| Pickup / arrival / started trip | Address, rider, ETA and navigation/safety above an independent stage-action footer. Arrival PIN remains with Start action. Keyboard inset is consumed. Cancel is only shown before trip start, matching backend rules. |
| Navigation beta | Map and instructions occupy measured areas, including side-by-side landscape. Follow GPS, Google Maps fallback and Return to trip remain. Android Back exits navigation. Missing route no longer says “Continue to destination”. |
| Completion | Clear estimate and no-real-payout copy; Done retained. |
| Earnings | Empty explanation, clearer estimate labels, removed outdated Build 24 text. Existing daily and weekly numbers retained. |
| Trips | Replaced blank empty screen with icon, explanation and Home action. Newest completed trips first; scrollable layout. |
| Account | Grouped documents and sign-in/logout within account list. Removed contradictory “documents not implemented” text. Existing profile edit, settings, safety and tax information retained. |
| Sign-in / registration / recovery | Keyboard-aware scroll layout and larger main action. Existing credential/session behavior retained. |
| Sign-in settings/logout | Loading indicator, Android Back and keyboard-aware scrolling; existing active-trip logout protection retained. |
| Onboarding/documents | Status panel, loading feedback, readable document labels, full-width submission/refresh controls, keyboard and Back handling. Upload/review/expiry API unchanged. |
| Shared appearance | Refined dark surfaces and text contrast, dark road map style, larger main action targets. Existing system light/dark behavior retained. |

## Passenger

| Screen/state | Review and change |
|---|---|
| Splash | Reviewed; branding/flow retained. |
| Welcome | Scroll and safe drawing insets prevent content loss on smaller displays. |
| Phone / verification / profile | Shared form safe-area and keyboard ordering improved. Primary actions can grow for text. |
| Home | Bottom card has a bounded scroll area so it cannot consume the whole map. Existing one-recent-place behavior retained. |
| Search | Keyboard inset, labeled Back/Clear actions, weighted result text, visible no-results guidance. Late autocomplete callbacks cannot replace a newer query's results. |
| Ride selection | Existing draggable sheet/sticky booking controls retained. Schedule/Choose divide available width and can grow vertically. Routing choices retained. |
| Schedule | Reviewed native date/time pickers, scroll and validation; retained. |
| Fare confirmation | Weighted summary label/value columns avoid long payment/status/trip values colliding. Existing fixed confirmation action retained. |
| Matching / active ride | Shorter title and clear matching copy; existing map, driver/PIN, cancellation and fare flow retained. |
| Trips | Consistent past-rides empty card and Find a ride action. Active/scheduled/history grouping retained. |
| Trip details | Missing-trip state now offers Back to trips. Receipt summary shares wrapping fix. |
| Account / saved places | Reviewed and retained; Back descriptions improved. |
| Payment methods | Scrollable add-card dialog; larger actions; existing selection order retained. |
| Account detail / appearance / language | Added scrolling so long content remains reachable. Theme behavior unchanged. Language switching remains the existing preview, not a new feature. |

## Deliberate limits

No new product features, new backend, migration, payout integration or new Admin version. Driver sign-in/logout, document review, multi-driver dispatch and Passenger features from Build 30 remain in the bundle. Road geometry depends on Google Routes API access; request acceptance does not depend on a successful route response. UI screenshots, Android compile success and physical-phone verification are not claimed.
