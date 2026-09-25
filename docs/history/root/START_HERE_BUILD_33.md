# Start RideNova Build 33

Build 33 upgrades the existing shared database in place. Passenger, Driver and Admin still use one Python server and one SQLite file.

## 1. Preserve private settings

Before replacing your old source folders, keep the two projects' private `local.properties` files and Passenger `gradle.properties` backend URL/Maps settings. This ZIP intentionally contains no private API keys, driver credentials or database.

## 2. Stop the older server

Close every older RideNova server terminal. Only one server should use port 8080. Back up your current SQLite database file, then open PowerShell in this extracted Build 33 root and run:

```powershell
$env:RIDENOVA_DEV_ADMIN_TOKEN = "your-existing-private-admin-token"
python START_SERVER.py --database "G:\RideNova\your-existing-database.sqlite3"
```

Use the same database path as Build 32. Build 33 adds one nullable, uniquely indexed phone column to driver logins; it does not erase passenger accounts, rides, documents, earnings or driver profiles.

Open `http://127.0.0.1:8080/health`. It must show `"version": "33.0"` and `"build": 33`. Admin is at `http://127.0.0.1:8080/admin` and should show **BUILD 33 · ADMIN v0.4.0**.

## 3. Build the Android apps

- Passenger project: `RideNovaPassenger_v0_23_Build23_Major` (actual app version **0.29.0-build33**).
- Driver project: `RideNovaDriver_v0_7_Build25_NavigationBeta` (actual app version **0.14.0-build33**).

The historical project directory names remain so existing Android Studio configuration is easy to reuse. Open each as a separate project. Copy only your own private settings; do not copy old source files over Build 33.

Driver `local.properties` should keep your SDK path, working Maps key and local server origin. Fleet sign-in does not use the old shared development driver token:

```properties
RIDENOVA_DEV_URL=http://127.0.0.1:8080
MAPS_API_KEY=YOUR_DRIVER_MAPS_KEY
RIDENOVA_LEGACY_DRIVER=false
```

Passenger `gradle.properties` must retain:

```properties
RIDENOVA_API_BASE_URL=http://127.0.0.1:8080
```

Run `powershell -File VERIFY_ANDROID.ps1`, then install/update both Debug apps. Keep installed apps if you want to preserve on-device settings. If testing the completely new driver entry flow, log out from Driver rather than clearing Passenger data.

## 4. Connect each phone

For every connected test device, run:

```powershell
adb -s YOUR_PHONE_SERIAL reverse tcp:8080 tcp:8080
```

Repeat after reconnecting wireless debugging or restarting the phone.

## 5. Test the Build 33 driver flow

1. Open Driver while the phone uses dark mode. Log out if an older driver is still signed in.
2. Open **Create account**, focus every field and keep the keyboard open. The whole screen must remain themed and scrollable; no white or blank half-screen should appear.
3. Create a development account using a unique username, Canadian phone number and 10+ character password.
4. Confirm the app enters the driver account. Complete document review/approval in Admin as in Build 32.
5. Go to **Account → Sign-in & logout**. Confirm the masked phone, document count, completed trips and estimated lifetime earnings appear.
6. Change the password, log out, then sign in once by username and once by phone.
7. Re-test one complete Passenger → Driver trip, including GPS, accept, arrive, PIN, start and complete.

Existing Build 32 username-only accounts remain valid. They do not gain a phone automatically. A real release will require verified phone ownership and production authentication rather than this development workflow.
