# RideNova Build 24 — Development operations milestone

## Exact versions
- Passenger Android **v0.23** (unchanged from Build 23.1)
- Driver Android **v0.6.1** (unchanged, including selected request tone)
- Shared Python backend **Build 24** (updated)
- Admin web portal **v0.1** (new, read-only)

## What's new
- An idempotent `development_earnings` SQLite ledger records a snapshot whenever the real driver completes a development ride. It stores subtotals, displayed GST, displayed passenger total, illustrative platform commission, and driver gross **before costs**. It records only new completions after the update, not retroactively migrated earlier trips.
- A token-gated read-only endpoint: `GET /v1/admin/overview` (Bearer `RIDENOVA_DEV_ADMIN_TOKEN`). Returns summary counts, current single development driver status, most recent 200 ride summaries, up to 200 ledger rows and totals for those displayed rows. This is not a full accounting journal or regulatory financial statement.
- Open the admin portal at `http://127.0.0.1:8080/admin` on the computer running the Python backend. Enter the development admin token and click Load dashboard. Refresh manually to see updates. Token lives only in the page memory, never in local storage.
- A new regression test validates duplicate ledger writes cannot double-count a ride.

## Upgrade carefully
1. Stop the old Python server. Back up the working backend folder and **the original SQLite database** (`ridenova-dev.sqlite3` by default, or your custom path), including WAL/SHM if present. If your deployment uses a custom MySQL-backed adaptation, **DO NOT overwrite it with this stock SQLite server**. This ZIP is based on the supplied Build 23.1 project, whose `backend/server.py` connects with `sqlite3`, not MySQL.
2. Replace the old shared backend with the Build 24 `backend` folder, or merge changes in a version-controlled working copy. Keep the original database and environment variables. No separate driver/admin backend is needed.
3. Use separate, nonempty values for `RIDENOVA_DEV_ADMIN_TOKEN` and `RIDENOVA_DEV_DRIVER_TOKEN`. Do not expose this development server on the public internet. It is loopback-only and lacks production admin authentication, roles, and auditing.
4. From the Passenger project root run `python -m unittest discover -s backend -p 'test_*.py'`.
5. Start normally, for example `python backend/server.py --database /path/to/existing/ridenova-dev.sqlite3 --port 8080` (replace path). Visit `http://127.0.0.1:8080/admin` on the same laptop.
6. Complete a NEW development trip on the existing apps, refresh portal and confirm one ledger row, correct displayed totals, ride state and driver status.

## Limitations and truth in labelling
This is a **development-only** milestone. No payment processor, actual capture, refunds or driver payouts are integrated. Pricing is the existing development quote policy; this release adds a completed-trip snapshot, not a fully finalized financial engine. Displayed GST/commission allocation needs proper professional review before real transactions. Admin v0.1 is read-only, and there is still just one development driver account. Backend remains SQLite. No new Android features were added or Android compiled in this milestone; both APK projects are carried forward unchanged. Next: Build 25 payments architecture, notifications, Admin v0.2, and proper admin authentication before any external deployment.
