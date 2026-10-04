# Start here — RideNova Build 42.1

This update improves your existing Build 42 product. It includes both Android apps, Admin and the same shared backend. It does not change the database schema, staff permissions, accepted fares or dispatch rules. It is still a controlled staging build; it does not enable public registration, live charges or payouts.

## 1. Preserve the working setup

Keep your existing Git repository, Render API, scheduler (if configured), PostgreSQL database and accounts. Make a backup of your current project and database using your existing backup procedure. Do not recreate the database, bootstrap an Owner again or re-enter driver accounts.

Keep your existing private `local.properties`, configured `gradle.properties`, signing configuration, `.env` values and Render environment variables. In particular, retain the Maps keys and `RIDENOVA_STAGING_API_BASE_URL`. The ZIP contains templates, not your private configuration.

## 2. Extract and update the code

Extract the ZIP under a short path such as `G:\RideNova`. It contains one folder, `RN421`. Open that folder and read this file. Avoid nesting it under several long folder names.

Copy the contents of `RN421` into the root of your existing Git checkout, where `Passenger`, `Driver` and `release.json` already live. Preserve the private configuration above. Keep your working `render.yaml` / free-preview configuration and existing service names; this UI release does not require a new Blueprint or a paid plan. Merge the new `.gitignore` entries with any exclusions you have added locally. Do not overwrite the repository's `.git` directory or copy build caches.

A new Git branch is useful for review, but a new repository is unnecessary. Review the differences, especially configuration, before committing. Commit source only: never keys, database exports, tokens or signing files. `CHANGELOG.md` describes the intended changes; `SOURCE_CHANGES_BUILD_42_1.txt` records the exact changed and added files relative to the corrected Build 42 source used here.

## 3. Verify and update the shared backend

From the repository root in PowerShell:

```powershell
python VERIFY_BUILD_42.py
```

This runs the portable backend tests and Admin/Android source checks. It does not need your laptop's live server; test servers and databases are temporary. The filename is retained for compatibility with your existing workflow.

Commit and push to your existing GitHub repository. The verification workflow now has the shared API job, Admin browser job and both Android jobs. Wait for all of them to pass before deploying your chosen commit.

Deploy that commit to your **existing** Render API service, and the same commit to your existing scheduler if you use one. Use your current deployment method and environment values. Do not change plans or deploy another Blueprint for this update. The current startup migration checks remain in place; Build 42.1 adds no migration beyond the existing `001`–`003` files. Their checksums and schema are unchanged.

Open your existing HTTPS API URL followed by `/health`: `version` should be `42.1`, `build` remains milestone `42`, and `releaseRevision` is `42.1`. The separate `revision` field in hosted WSGI remains the deployed Git commit, for scheduler/deployment checks. Open `/admin` and hard-refresh once to load the new portal. Your Owner/staff credentials stay the same.

## 4. Rebuild and install both staging apps

Keep the same application variants and signing keystore as the installed apps. Open `Passenger` and `Driver` as separate Android Studio projects. Select **staging**, check the existing Render URL and Maps setup, and build/install both apps as updates. Do not uninstall or clear data just to install this UI update.

Alternatively, from the repository root in PowerShell, using the staging URL already configured in each project's Gradle properties:

```powershell
Push-Location Passenger
.\gradlew.bat assembleStaging
Pop-Location
Push-Location Driver
.\gradlew.bat assembleStaging
Pop-Location
```

Use a full JDK 17 and the SDK versions requested by the existing project. The staging APK for each project is under `app\build\outputs\apk\staging\`. No APK is distributed in this ZIP: internal compilation used an intentionally invalid example URL and no real Maps key. Build with **your** configured URL and key before installing.

Staging retains `.staging` package names. Keep the correct package/SHA-1 restrictions already configured for Maps. Debug defaults to local development; it is not a substitute for the configured staging variant. When both staging apps point to Render, your laptop does not need to run the backend.

## 5. Run the acceptance checklist once

Use `MANUAL_TEST_CHECKLIST_BUILD_42_1.md`. It focuses on keyboard open/close, text sizing, offers, history navigation, payment messaging, Admin refresh and account continuity. The automated results are in `TEST_RESULTS_BUILD_42_1.md`.

This update is source-complete and automatically checked as described there. Android device visuals, your live Render response time and real Stripe sandbox interactions still require testing in your configured environment. Existing accounts and trips should remain; if any appear missing, stop and check that the same API URL and database are selected before creating replacements.
