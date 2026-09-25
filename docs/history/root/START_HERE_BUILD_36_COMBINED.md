# RideNova Build 36 — Combined Driver stability and Admin 2.0 UI

Baseline: user-supplied Build 35. Existing Passenger app, shared backend, dispatch, database schema and driver features retained.

## Driver
- Floating shortcut uses `ic_ridenova_driver`, the exact drawable referenced by the app launcher, with explicit oval outline and clipping.
- Driver main screen no longer applies keyboard inset twice at the root; the active ride screen owns its keyboard inset and PIN action region.
- Authentication list owns keyboard inset and scrolls back on dismissal.

## Admin UI
- Left navigation with dedicated Overview, Live operations, Rides, Drivers & applications, Earnings & finance, Support and Trip feedback pages.
- Existing tables, controls, document reviews, endpoints and admin-token requirement preserved by moving DOM nodes (not cloning).
- Ride table limited to 25 rows per page after existing status filtering. This is browser-side pagination only; server-side pagination remains future work.
- No individual staff accounts, RBAC or real payment processing are claimed or introduced. Do not expose development portal publicly or share token with additional operators.

## Verification required
Android Studio: Gradle sync and compile Driver; test sign-in keyboard show/hide, sign-up, PIN keyboard show/hide on a physical phone, bubble shape/artwork. Admin: open /admin, load dashboard, test sidebar, review driver, status filter, paging and support. Run backend unit tests in project root using `python -m unittest discover -s backend -p "test_*.py"`. Keep database backup.
