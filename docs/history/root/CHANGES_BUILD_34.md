# Build 34 changes

## Passenger 0.30.0

- Added a post-trip experience card to completed trip details.
- Added editable 1–5 star driver ratings, structured tags and an optional 500-character comment.
- Added trip-linked support intake for lost items, fares, safety, driver concerns and app issues.
- Added support-case counts to the completed-trip experience.
- Kept the detailed receipt, route preview, payment snapshot and Ride again workflow.
- Feedback and support dialogs scroll and use IME padding so the keyboard does not hide input.

## Driver 0.15.0

- Added rider ratings to both the trip-complete card and trip history.
- Added structured rider feedback and optional private comments.
- Added trip-linked support cases for passenger, safety, fare/earnings and app concerns.
- Added clear success/error states and keyboard-safe dialogs.
- Preserved Build 33 authentication, logout/account switching, documents, GPS, dispatch and trip recovery.

## Backend 34.0

- Added durable `ride_feedback` and `support_cases` SQLite tables with automatic migration.
- Added passenger and fleet-driver feedback/support APIs with ownership checks.
- Ratings require a completed ride and the actual passenger/assigned driver relationship.
- One rating per side per ride is enforced atomically and can be updated.
- Added validation for stars, tags, descriptions, comments, categories and Admin state changes.
- Added Admin feedback/case endpoints and experience metrics in the operations overview.

## Admin 0.5.0

- Added rating count and average-rating metrics.
- Added Open and In-review support counts.
- Added a feedback review table.
- Added a support queue with In review / Resolve actions and Admin notes.
