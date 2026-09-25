# RideNova Build 38.1 — Windows test-suite hotfix

Baseline: user-supplied RideNova Build 38/39 combined ZIP. This release changes ONLY four backend test files; production backend code, apps, admin UI and database files are unchanged.

## Changes
- `Passenger/backend/test_build29.py`: Explicitly close the raw SQLite connection created for the Build 28 migration test using `contextlib.closing`, after transaction handling, before temporary-folder cleanup.
- `Passenger/backend/test_build29.py`, `test_build31_1.py`, `test_build34.py`, and `test_server.py`: Legacy HTTP tests explicitly clear `RIDENOVA_OWNER_USERNAME` and `RIDENOVA_OWNER_PASSWORD` only while constructing their own isolated test HTTP handler. This makes their legacy-token expectations independent of the user's PowerShell Owner bootstrap environment. Actual Owner bootstrap, staff sessions, role checks and invalid-token behavior remain enforced and continue to have independent coverage in `test_build38_39.py`.

## Run on Windows
1. Stop the running backend before testing, and keep a backup of your existing database.
2. Extract the ZIP to a SHORT path (e.g. `G:\\RideNova\\Build38_1`).
3. Open PowerShell in the extracted `Passenger` folder (the folder containing `backend`).
4. Run `python -m unittest discover -s backend -p "test_*.py"`.
5. Expect `Ran 121 tests ... OK`. This has passed in the build environment but Windows must be verified on the user's machine.

Do not delete or reset your database. You can instead copy the four modified `test_*.py` files over the same files in your working Build 38/39 folder; no Android rebuild is needed.

## Verification
- Python 3: 121/121 tests passed in this environment.
- Windows file-lock behavior: requires confirmation on Windows.
- Backend production code and app functionality: unchanged.
