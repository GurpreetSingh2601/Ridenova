# RideNova v0.21.2 — Stable card selection

This hotfix builds on v0.21.1 and includes all prior passenger UI changes. It fixes payment-card rows jumping to the top after you select them. Card order now stays as added; the checkmark and highlighted border move to your selected card, like RideNova's ride-category cards. The selected card remains your default for future development rides. No real payment is processed.

## Keep your accounts, cards, places and trips

1. Extract this ZIP and open `RideNova_v0_21_2_Payment_Selection_Hotfix` in Android Studio.
2. Copy your existing private `local.properties` into this project, and ensure its project-level `gradle.properties` still has the working phone connection URL:

```properties
RIDENOVA_API_BASE_URL=http://127.0.0.1:8080
```

3. Stop your old Python server with Ctrl+C. Start **this ZIP's** `backend/server.py` using the full path of the same SQLite database you were using before:

```powershell
python backend/server.py --database "G:\path\to\your\existing\ridenova-dev.sqlite3"
```

If you used an admin simulator token, set `RIDENOVA_DEV_ADMIN_TOKEN` in this Terminal before launching Python. Leave the server running. Opening `http://127.0.0.1:8080/health` on the laptop should report `0.21.2`. Do not delete your original SQLite file or start in an unintended folder without `--database`.

4. If wireless debugging reconnected, run `adb reverse tcp:8080 tcp:8080` again for your phone. Sync Gradle, rebuild and run the updated Android app (version 0.21.2, versionCode 24). **Do not uninstall or clear app data.**
5. In Payment methods, tap the lower card and verify it stays in place while the highlight and checkmark move to it. Go back to booking confirmation and verify it displays that card. Restart the app and verify the order and selection remain unchanged.

The SQLite schema and payment behaviour are unchanged; only card ordering and visual selection were adjusted. Historical instructions are in `START_HERE_v0_21_1.md` and `START_HERE_v0_21.md`.
