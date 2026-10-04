# RideNova Build 42.1 — UI and UX refinement

Release date: 2026-10-03 UTC. This extends the corrected Build 42 source; Build 43's safety/sharing/boost experience remains a separate roadmap milestone.

| Component | Version |
|---|---|
| Passenger | 0.34.1-build42.1 · code 45 |
| Driver | 0.19.1-build42.1 · code 41 |
| Shared API | 42.1 |
| Admin | 0.9.1 |

## Passenger

- Consistent launcher artwork in welcome/authentication/home branding; the existing logo assets and Canadian tagline are preserved.
- Shared type scale, charcoal surfaces, clearer light theme, spacing, corner shapes and error notices.
- Bounded-width, scrollable authentication/profile forms with keyboard actions and disabled/loading submit states.
- Clearer home hierarchy and readable branding over the map; selectable ride cards expose radio-button semantics.
- Booking quote, GST-inclusive total, missing-payment guidance and error messages have a clearer hierarchy. No fare formula or quote binding changed.
- Payment setup explains the Stripe handoff and return-to-verify step. Completed-trip authorization describes `requires_capture` in human language.
- Trips gains All/Completed/Cancelled filtering; active and scheduled sections remain available. Account rows and long names are easier to scan.
- Rating and support dialogs keep errors next to the action, prevent repeated submission while busy and support scrolling; post-trip rating remains available.

## Driver

- Sign-in now uses the actual Driver launcher artwork and the shared design language. Removed the forced jump to the top when the keyboard closes; consumed Scaffold insets before applying IME padding.
- Home/Earnings/Trips/Account bottom navigation is available when idle or after completion. Offers and active navigation retain dedicated space.
- Incoming offers use an adaptive map/details layout with fixed Accept/Decline controls. Dense details can still scroll on small screens or enlarged text; landscape uses two columns where space permits.
- Cleaner offer hierarchy, countdown, route, estimated earnings and per-offer hourly equivalent; Trip Radar stays distinct from exclusive offers. Dispatch behavior is unchanged.
- Earnings has a clearer summary and period controls; earnings rows open trip details. History has address/ID search and useful empty states. Rating/support actions live in the trip detail screen.
- Trip-detail Back returns to history; leaving details through the drawer clears the selected trip correctly.
- Documents shows review progress; active/completed trip states and online status are clearer. Alerts, shortcut, GPS, routes and account access retain their existing functionality.

## Admin

- Refined sign-in, sidebar, icons, workspace headings, tables, forms, empty states, status badges and responsive mobile navigation across all nine workspaces.
- Refresh in each workspace; last-updated time; coalesced duplicate refreshes; explicit stale-data error when a refresh fails.
- Refresh loads the current workspace instead of fetching every area. This reduces unnecessary Admin requests; it is not a measured fix for all hosted or Android latency.
- Expired sessions return to sign-in and clear loaded records. In-flight responses from an old session cannot refill the cleared workspace.
- Owner and restricted roles retain the same server-enforced permissions. No default credentials, permission bypass or public signup has been introduced.
- Finance translates authorization status and fills empty event/balance/zone areas with useful guidance. Existing capture/refund/reconciliation and boost controls are preserved.

## Preserved integration

One backend, the existing `001`–`003` migrations, account/session contracts, dispatch, pricing and financial idempotency remain. The corrected PostgreSQL finance-summary serialization is included. No database or secret is bundled, no hosted deployment was made and no cloud plan was changed.

See the screen inventory and research in `DESIGN_RESEARCH_AND_AUDIT.md`, actual test results, known limitations and the manual acceptance checklist.
