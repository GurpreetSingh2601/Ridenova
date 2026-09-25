# RideNova Build 39 — Admin role clarity / operations UX increment

Base: the supplied Build 38.2 project. This is a **scoped Build 39 increment**, not completion of every feature proposed in the roadmap. It preserves Passenger, Driver and shared backend as supplied; no database migration or reset, no Android rebuild is required for these changes.

Changes: Owner role selection now shows the assigned role's practical access before staff creation; read-only Compliance users no longer see the Ride types driver mutation button; detailed staff permission and test documentation added. Backend authorization, staff sessions, ride matching and database schema remain unchanged.

Run from Passenger directory: `python -m unittest discover -s backend -p 'test_*.py'`. Start the usual server with your **existing database path**, sign in as Owner to `/admin`, hard-refresh (`Ctrl+F5`) and inspect Staff & access. Test each role separately. Preserve your existing DB, environment settings and `local.properties`. Do not publicly expose this development server.

Deferred versus original proposed Build 39: new server-side pagination for fleet/support, additional Driver and Passenger reliability features, and comprehensive Windows/real-device acceptance have **not** been implemented in this increment. Build 40 may address them after testing and a user-approved scope.
