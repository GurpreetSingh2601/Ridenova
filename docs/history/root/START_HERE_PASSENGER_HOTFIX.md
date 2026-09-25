# RideNova Build 25.1 — Passenger backend-mode configuration fix

Corrects a packaging/configuration regression: the Build 25 Passenger Gradle file did not define `RIDENOVA_API_BASE_URL`, so the app selected the obsolete offline prototype and displayed manual Demo buttons and simulated driver identity. The updated Passenger is v0.23.1. Driver v0.7, Admin v0.1 and shared backend are retained.

## Install
1. Back up your current project and SQLite database. Extract this ZIP to a NEW folder; open `RideNovaPassenger_v0_23_Build23_Major` as its own project in Android Studio.
2. In **the Passenger project** `gradle.properties`, add `RIDENOVA_API_BASE_URL=http://127.0.0.1:8080` if using a USB/wireless-debugging ADB reverse tunnel. Run `adb -s DEVICE_SERIAL reverse tcp:8080 tcp:8080` for the actual Passenger device, replacing `DEVICE_SERIAL`. ADB reverse must be active when testing.
3. If using home Wi-Fi without ADB reverse, instead use `RIDENOVA_API_BASE_URL=http://YOUR_COMPUTER_LAN_IP:8080`; configure the server to listen on the LAN and use appropriate firewall settings. Never use this private IP outside the LAN.
4. Preserve your real `MAPS_API_KEY` in Passenger `local.properties`, and your existing DRIVER settings separately in the Driver project. Do NOT put a driver or admin token into Passenger configuration.
5. Gradle Sync, **Build > Clean Project**, uninstall the old Passenger APK from the test phone, then install the newly built v0.23.1 APK. Uninstalling can clear local app data: ensure your test account/session can be recreated and back up anything you need.
6. Start the existing shared backend; verify `http://127.0.0.1:8080/health` in the computer browser. Open Driver v0.7 and go online; allow precise location, foreground service notifications and observe a fresh GPS report. If Driver is offline or GPS is stale, Passenger correctly displays no nearby driver: this is a separate availability state, not proof of demo mode.
7. Book a test ride, accept in Driver. Passenger must show server-controlled ride updates with **no 'Demo: driver has arrived'** button. Driver position requires the phone to have current GPS, permissions, working backend connectivity and an active ride.

## Configuration guard
Build now fails explicitly if `RIDENOVA_API_BASE_URL` is missing, rather than silently running the offline prototype. No data migration or database reset is required. This does not claim to fix other potential issues with GPS service or network connectivity.

## Verification
The source of the old mode was identified by comparing Build 23.1, 24 and 25 passenger files, all identical. Passenger factory previously used PrototypeRideNovaRepository when backend URL blank. The build and factory now reject blank configuration. Android Gradle compilation and phone integration must still be verified on your workstation.
