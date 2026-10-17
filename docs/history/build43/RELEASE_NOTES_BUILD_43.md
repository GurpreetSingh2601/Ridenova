# Build 43 — Pickup and trip reliability

Baseline: the accepted complete Build 42.1 UI/UX archive. Existing branding, shared backend, Admin roles, Stripe test integration and capped boost foundation are retained.

## Seven fixes

1. **Editable pickup:** search an address, tap a map point, move the map, or explicitly use current GPS. Confirm before changing the booking. Home, ride selection and confirmation expose the editor.
2. **Manual pickup protection:** GPS callbacks cannot silently replace a manual selection. A changed pickup discards the old route/quote and returns through route selection for a new fare review.
3. **Location fallback:** missing/denied GPS, inaccurate fixes and timeout have actionable manual alternatives. Home/editor reject fixes older than 60 seconds or with reported accuracy worse than 100 metres. Staging does not substitute sample search destinations when Places is unavailable.
4. **Pickup instructions:** up to 280 characters, stored with the authoritative quote and booked ride, visible to the assigned driver and permitted Admin ride viewers. Submitted booking payloads cannot overwrite quoted instructions.
5. **Immediate driver rating:** optional, initially unselected stars on the completed-trip card; submit, skip, retry and saved-rating confirmation. Existing history feedback and support remain available. No automatic five-star submission.
6. **Draft recovery:** pickup/manual selection, destination, tier, schedule and instructions survive recreation. Home offers Continue booking. Expired schedules reset to Now; quotes and route estimates are not persisted. Draft clears after successful booking and on sign-out.
7. **Honest status labels:** arrived/in-progress/cancelled status no longer reuses a pickup ETA label; staging simulated payment records are distinguished from Stripe test authorization. No-show has its own history/Admin state. Restored active-driver trips use the pickup street address and available rider first name.

## Larger flow: waiting and rider no-show

A verified arrival starts a five-minute **server** timer. Driver GPS must be no older than 30 seconds and within 250 metres of pickup at verification and cancellation. An unverified/legacy arrival requires a new verified timer. Repeated arrival does not restart a valid timer. These checks do not prove uninterrupted presence between those moments.

The driver checks the pickup/instructions and selects an explicit reason before cancelling. A transaction permits only one winning transition when start, passenger cancellation or no-show compete. Retries return the same no-show result without duplicate events or earnings. Passenger sees the no-show outcome, can book again and can access trip Support. Admin shows notes, reason, verification time and the zero fee. This path records no waiting/no-show fee, earnings or boost award. It does not claim to contact the passenger or refund a provider payment automatically.

Passenger 0.35-build43 (46); Driver 0.20-build43 (42); API 43; Admin 0.10.0. No schema migration added. See actual verification results and manual acceptance checklist.
