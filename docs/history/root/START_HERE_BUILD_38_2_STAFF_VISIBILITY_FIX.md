# RideNova Build 38.2 — Staff & access UI visibility fix

Baseline: corrected Build 38.1 Windows Test/Auth ZIP.

## Correction
The `#staff-workspace` section was initially marked `hidden` in Admin HTML and was moved into the sidebar page without removing that attribute. The Staff page heading therefore appeared while its account form, directory and audit section stayed hidden. The navigation setup now unhides this section before inserting it into the Staff page; the parent workspace still controls whether the Staff page is visible. Backend roles, authentication and database are unchanged.

## Install
Stop the backend. Replace ONLY `Passenger/backend/admin/index.html` in your currently running Build 38.1 project with this file. Restart your existing backend; reload `/admin` with Ctrl+F5; sign in as Owner; select Staff & access. Do not reset the database or owner account. The full ZIP is also supplied for convenience.

## Verification
Run `python -m unittest discover -s backend -p "test_*.py"` from the Passenger project directory on Windows. Check that Staff & access displays the form, directory and audit listing. Create a test Support account; verify it cannot use Owner-only staff administration endpoints. Do not expose the development server publicly.
