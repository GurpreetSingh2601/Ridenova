# RideNova design research and screen audit

Research and source audit for Build 42.1, 2026-10-03 UTC. The authoritative implementation was the corrected local Build 42 bundle, including the populated PostgreSQL finance-summary fix. Earlier conversation claims were not treated as proof that a feature exists.

## References and decisions

| Official reference | Relevant pattern | RideNova application |
|---|---|---|
| [Uber app redesign](https://www.uber.com/ca/en/newsroom/were-redesigning-the-uber-app-just-for-you/) | Clear home priorities, frequent destinations, easier activity access | Readable map/home entry, retained saved places, trip filters and clear navigation |
| [Lyft upfront pay](https://help.lyft.com/hc/en-us/driver/articles/8668928544-Upfront-pay) | Route and earnings information before accepting an offer | Preserve pickup/drop-off, distance/time, estimated earnings and timer; keep Accept/Decline fixed |
| [Uber for Business hub](https://www.uber.com/ca/en/business/products/business-hub/) | Centralized reporting and account/access management | Organized role-aware Admin workspaces and explicit data freshness |
| [Android Material 3 insets](https://developer.android.com/develop/ui/compose/system/material-insets) | Avoid duplicate insets and respect keyboard/system areas | Consume Scaffold insets in Driver access and use one scrolling form container |
| [Compose accessibility defaults](https://developer.android.com/develop/ui/compose/accessibility/api-defaults) | Semantics, touch targets and readable interaction states | Radio semantics, headings/live notices, keyboard actions and fixed accessible offer controls |

These are public references, not access to Uber/Lyft's private Admin designs or evidence of their internal architecture. RideNova retains its own logo, colours, flows and server contracts; no competitor assets were copied. No claim of superiority or comprehensive accessibility certification is made.

## Design system

Dark charcoal backgrounds, raised slate surfaces, periwinkle primary actions, strong white text and a coordinated light theme. Both apps share the same typography sizes/line heights and corner scale. The existing Passenger/Driver vector launcher assets are reused inside the apps; the Driver steering-wheel identity is preserved. Admin uses the matching RideNova mark and consistent line icons.

Primary actions have explicit disabled/loading states. Errors appear near the relevant action; empty states explain what to do next. Motion is restrained; Admin respects reduced-motion settings. Maps retain their existing pan/recenter behavior and transport integrations.

## Audited screen inventory

| Surface | Implementation in this update | Scope/boundary |
|---|---|---|
| Passenger welcome/splash | Logo consistency, faster entry, existing tagline | Existing navigation retained |
| Phone/code/profile | Shared form layout, keyboard actions, loading/error clarity | Invitation/SMS rules preserved |
| Home/search/saved places | Home hierarchy and legible map brand; shared type/surfaces across search/place sheets | Search/provider logic unchanged |
| Ride selection/scheduling | Selectable card semantics and shared visual scale | Existing scheduling limits retained |
| Booking/fare/payment selection | Quote/GST hierarchy, missing-payment notice, busy button | Server price and route binding unchanged |
| Matching/assigned/arrived/on trip | Shared theme and clearer shared states | No new dispatch or GPS algorithm |
| Completed trip/history/details | Filtering, receipt hierarchy and rating/support dialog states | Prior trips preserved; no fabricated route data |
| Payment setup/test authorization | Checkout return/verify guidance, useful empty state, human-readable authorization | Stripe test flow preserved |
| Account/profile/places/appearance/language/help/safety | Shared surfaces/type; account rows and long-name layout refined | Placeholder services remain placeholders |
| Driver sign-in/signup/recovery | Canonical logo, form hierarchy, keyboard-close behavior | Development registration, invited staging sign-in |
| Driver idle home/menu | Bottom tabs, branded drawer, explicit online status | Existing home map/quick actions retained |
| Exclusive/Radar requests | Adaptive map/details, compact card, fixed actions, busy/expired state | Atomic server assignment unchanged |
| Pickup/arrive/PIN/on trip/navigation | Shared type/surfaces, live status notice | Existing trip state machine preserved |
| Completed/earnings/history/detail | Summary hierarchy, period controls, trip entry, search, empty states, back behavior | Gross estimates remain estimates |
| Driver documents/account/alerts | Review progress and shared visual treatment | Existing upload, account and shortcut functionality |
| Admin sign-in/out | Auth layout, keyboard submit, identity and clear session ending | Backend staff authentication retained |
| Dashboard/live operations | Metric cards, workspace description, current-page refresh/freshness | Server aggregates remain authoritative |
| Rides/fleet/documents | Search/table states, row keyboard access, responsive layout | Existing filters/review/eligibility endpoints retained |
| Finance/boost | Consistent controls/status wording and empty guidance | Test-only, Owner mutations/Finance reads |
| Support/feedback/staff/audit | Shared table/form/empty treatment and role navigation | Existing server roles preserved |

## Validation and remaining design work

The Admin was rendered in Chromium at 1440px and 390px using fixture records. Both Android apps compiled in debug and staging. Physical-device rendering was not performed, so keyboard, large-text and accessibility acceptance are explicitly listed in the manual checklist.

Build 42.1 is an incremental design pass. The later safety, boost-map, support, navigation/performance and public-onboarding roadmap items are not represented as implemented by this work. Admin request reduction is concrete; no universal app speed claim is supported without hosted measurements.
