# RideNova Passenger architecture — Build 41

- Jetpack Compose screens consume repository interfaces rather than owning server rules.
- `BackendRideNovaRepository` sends selected-route data, parses server quotes/trips, and retries an ambiguous create exactly once with the same quote token.
- `RideNovaHttpClient` handles JSON transport and authenticated token refresh.
- The shared Python service is authoritative for route acceptance, pricing, GST, booking idempotency, trip state, assignment and history.
- Access/refresh tokens represent passenger sessions; Android Keystore protects locally stored token material.
- The app polls/reloads backend rides to recover active state after navigation or process restart.
- Google Maps/Places/Routes provide Android map/search/road geometry in development. Production routing belongs behind the secure backend.

The server, Driver and Admin architecture and non-negotiable rules are defined in repository-root `RIDENOVA_DEVELOPMENT_RULES.md`.

