# Build 40 Windows verification correction

The oversized-request negative test previously sent a large body while the
server rejected its Content-Length and closed without reading that body.
On Windows this can produce WinError 10053 before urllib sees the HTTP 413.

The test now sends only the oversized request headers, waits for the early
rejection and explicitly checks both HTTP 413 and BODY_TOO_LARGE. It does not
swallow connection errors or treat a network failure as a passed test.
The positive path still sends the entire 2,001-point route to quotes, confirms
with a compact booking request, verifies the stored route and fare and checks
that retrying produces only one ride.

This correction changes test code and documentation only. Passenger stays at
0.32.1-build40; no app rebuild, server update or database migration is needed if
you already installed the booking correction.

For an existing Build 40.1 folder, copy only Passenger/backend/test_build40.py
from this full ZIP over the same file, then run python VERIFY_BUILD_40.py from
your existing project root. Preserve your local configuration and database.

Linux verification is recorded in verification/build40-windows-fix-tests.txt.
Windows verification must be rerun on your PC; it has not been executed here.
