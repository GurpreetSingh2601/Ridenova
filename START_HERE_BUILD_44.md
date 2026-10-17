# Start here — RideNova Build 44

One bundle contains Passenger, Driver, Admin and ONE shared backend at `Passenger/backend`. Keep the same GitHub repository, existing Render services/database, accounts, secrets, invitations, Stripe test settings, Android keys and signing keystore. No new Owner or driver accounts, database or Blueprint is needed. Nothing has been deployed or purchased here.

## 1. Back up first

Record the accepted Build 43 Git commit. Back up your existing database and private Android settings/signing key outside Git. Use `Passenger/backend/tools/backup_restore.py backup <path>` with `DATABASE_URL` set privately and a compatible PostgreSQL client. Verify restoration into a separate disposable database. Never restore over your live database. For SQLite development, stop the local server and copy the closed database or use SQLite's backup API. This ZIP contains no blank replacement database.

## 2. New folder, same repository

Extract the archive to `G:\RideNova\Release44` (inside is `RN44`). Clone the existing repository into a new working folder, replacing the example URL:

```powershell
Set-Location G:\RideNova
git clone https://github.com/YOUR-ACCOUNT/YOUR-EXISTING-REPO.git RN44Work
Set-Location .\RN44Work
git switch -c build44
```

Copy the extracted RN44 contents into RN44Work, replacing matching source files and preserving `.git`. Restore private `Passenger\local.properties`, `Driver\local.properties` and signing keys from your working installation. Keep your configured `render.yaml` and service plans. Transfer only needed private Gradle property values; do not overwrite the new Gradle source files with old copies. Do not copy old build/cache directories or databases.

```powershell
git status
python VERIFY_BUILD_44.py
git diff --stat
```

Verification uses isolated temporary test data. Your laptop server is not needed. Python and Node must work in this terminal. The old verifier filenames forward to Build 44.

## 3. New browser Maps configuration

Keep Android Maps keys unchanged. For Admin and shared-trip web maps, configure a Google Maps JavaScript API browser key with HTTP-referrer restrictions to your exact existing Render/custom-domain origin and API restriction to Maps JavaScript API. Set `RIDENOVA_MAPS_BROWSER_KEY` on the existing API service. Browser keys are visible by design; never use an unrestricted server key, Stripe secret or Android-only key here.

Review Google billing/quota before enabling the API. Nothing was enabled here. No additional Render service is required. Without this key the records/timeline remain accessible, but the map shows a configuration error. Google routes are displayed only on Google Maps.

## 4. Build both staging apps

Use full JDK 17 and your existing SDK/settings. Replace the URL with your actual Render origin, without `/admin`:

```powershell
$api = 'https://YOUR-EXISTING-API.onrender.com'
Push-Location Passenger
.\gradlew.bat assembleStaging "-PRIDENOVA_STAGING_API_BASE_URL=$api"
Pop-Location
Push-Location Driver
.\gradlew.bat assembleStaging "-PRIDENOVA_STAGING_API_BASE_URL=$api"
Pop-Location
```

APKs are under each project's `app\build\outputs\apk\staging\`. Install as updates using the same signing key; do not clear account data unnecessarily. Staging connects to Render without a laptop server or ADB reverse. Debug defaults to local development. This source ZIP does not contain configured installable APKs or private keys.

## 5. Review and push

Review changes for secrets, databases, `.env`, local.properties, dumps and keystores before staging. Keep them out of Git.

```powershell
git add .
git diff --cached --stat
git status
git commit -m "RideNova Build 44 safety operations and documents"
git push -u origin build44
```

Open a PR to your existing deployment branch. Wait for shared API/PostgreSQL, Admin browser and both Android jobs to pass. Coordinate merging if automatic deployment is enabled.

## 6. Migrate and deploy the same database

Pause trip testing and stop the old scheduler during rollout. Verify your backup. Migration `004_safety_operations.sql` adds tables/indexes; 001–003 retain their checksums. Existing accounts, trips, payments and staff remain in place.

The existing Blueprint's pre-deploy command `python migrate.py` applies pending migrations. If your service lacks pre-deploy support, run it from `Passenger/backend` through the existing authorized deployment workflow or terminal with the same private database URL, before starting Build 44. Use the internal database URL inside Render; external URL only for permitted external tools. Do not run the SQLite importer against an occupied Render database.

Deploy the same reviewed commit to your EXISTING API and scheduler, then resume the scheduler and install both staging app updates. Keep current secrets/invites/plans. Do not create a new Blueprint or upgrade a plan simply to install this release. Continuous reminders/retention require the existing scheduler; without it, eligibility checks still run on API actions, but timely reminders/cleanup are not guaranteed. No scheduler purchase was authorized here.

## 7. One acceptance pass

Check `/health` reports build/version/releaseRevision 44, `/ready` under your scheduler setup, and Admin shows `BUILD 44 · ADMIN v0.11.0`. Use the same Owner credentials. Follow MANUAL_TEST_CHECKLIST_BUILD_44.md with invited testers and synthetic documents.

Rollback: retain old code and backup, stop testing, roll back compatible code coherently and retain additive tables. Do not drop tables or restore an older backup over newer trips/payments. Prefer fix-forward or rehearse recovery into a separate database. This is a staging candidate, not public-launch approval.
