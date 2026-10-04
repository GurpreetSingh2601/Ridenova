# Start here — RideNova Build 43

This is one integrated source update for Passenger, Driver, Admin and the existing shared backend. No separate Driver server, new database or new GitHub repository is needed. Nothing has been deployed to your Render account by this work.

## 1. Back up your working setup

Keep the accepted Build 42.1 source, current Git commit, both Android signing keys, local configuration and a verified database backup. Use your existing PostgreSQL backup procedure. The bundled `Passenger/backend/tools/backup_restore.py backup <file>` reads `DATABASE_URL` from your private environment and creates a dump plus checksum/inventory manifest; `restore-check <file>` uses **a separate empty** `RESTORE_DATABASE_URL` and refuses an occupied target. Never restore over the current database. Never commit these backups or connection strings.

Build 43 needs **no new migration**. The existing migration files 001–003 are unchanged. New pickup notes and waiting fields are additive values in the existing JSON ride/quote payloads. Existing accounts, staff credentials, payment records and trips remain in the same database.

## 2. Extract and update the existing repository

Extract into a short path such as `G:\RideNova\RN43`. This extracted folder is not automatically a Git repository. Copy the release files into your existing checkout, preserving its `.git`, private `local.properties`, private Gradle settings, environment files and signing keys. Do not copy old build/cache directories over this release. Use the same repository and branch workflow you already use.

From the repository root in PowerShell:

```powershell
git status
python VERIFY_BUILD_43.py
git diff --stat
```

`git status` confirms the repository and shows changed files. Verification runs temporary backend tests and source checks; your laptop's live server is not needed. Review the changes locally and ensure no secrets/databases are staged. The older `VERIFY_BUILD_42.py` entry point forwards to the current checks.

## 3. Compile both staging apps with your existing settings

Keep the current Maps key, staging URL, package names and signing keystore. Use a full JDK 17, not a Java runtime without `javac`. Keep the existing Maps package/SHA-1 restrictions for both `.staging` apps. Debug defaults to local development.

```powershell
Push-Location Passenger
.\gradlew.bat assembleStaging
Pop-Location
Push-Location Driver
.\gradlew.bat assembleStaging
Pop-Location
```

These commands read your existing `RIDENOVA_STAGING_API_BASE_URL` configuration. If not configured, pass `-PRIDENOVA_STAGING_API_BASE_URL=https://YOUR-EXISTING-API.onrender.com` to each Gradle command. Replace the placeholder with your real HTTPS origin. APKs appear under each project's `app\build\outputs\apk\staging\`.

No usable APK is bundled: compilation here uses `https://staging.example.invalid` and no Maps key. Install your locally configured APKs as updates with the same signing key; do not uninstall or clear account data unnecessarily.

## 4. Roll out apps and backend together

**Update both invited test apps before enabling Build 43 on the server.** The new Passenger understands `CANCELLED_NO_SHOW`; older Passenger versions may fail to parse that status. Temporarily avoid trip testing during rollout. Against an older API, the new Driver's waiting card will report unavailable until the backend update arrives; this is expected.

Commit only reviewed source files and push to the same repository. Example after reviewing staged files:

```powershell
git add .
git diff --cached --stat
git status
git commit -m "RideNova Build 43 pickup and trip reliability"
git push origin main
```

Use your actual branch if different. Wait for the shared API, Admin browser and both Android GitHub Actions jobs to pass. Deploy that exact commit to your **existing Render API** and the same commit to your existing scheduler if used. Keep the current database, secrets, invitation values, Stripe test configuration and plan. Do not deploy another Blueprint merely to apply this update. If automatic deployment is configured, coordinate the app updates before pushing the deployment branch.

## 5. Confirm the hosted update

Your existing `/health` must report build `43`, version `43` and releaseRevision `43`; hosted `revision` remains the Git commit. Check `/ready` using your existing scheduler configuration. Open `/admin`, hard-refresh, and verify `BUILD 43 · ADMIN v0.10.0`. Sign in with the same Owner/staff account.

The staging apps use Render when configured with its URL, so the laptop does not run their backend. No-show waiting is checked on API requests; it does not add a new continuous worker or charge.

## 6. Run one acceptance pass

Use `MANUAL_TEST_CHECKLIST_BUILD_43.md`. Check manual pickup, map/permission failures, draft recovery, notes, ratings, normal completion and the five-minute no-show path. Compare the result with `TEST_RESULTS_BUILD_43.md` and `KNOWN_ISSUES_BUILD_43.md`.

If accounts appear missing, first check the API URL and database; do not create replacements. For rollback, retain both release sources and a backup. Do not delete no-show records to make old apps parse them. Keep Build 43 Passenger installed when rolling back the backend, or fix forward. Financial provider tests and device acceptance are separate from automated tests.
