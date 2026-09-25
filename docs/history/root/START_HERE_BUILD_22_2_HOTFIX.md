# RideNova Build 22.2 Hotfix

Passenger v0.22.2 + Driver v0.5.1 + shared backend update.

## Nearby-driver ETA fix

- Removes the fixed 3/5/7-minute pickup ETA from the Passenger booking summary.
- Passenger polls the shared backend every 5 seconds while the booking summary is open.
- The backend returns availability only when the development driver is online, idle, and has published a location within the last 30 seconds.
- Pickup ETA is calculated from the driver’s latest GPS position to the passenger pickup location.
- If the driver is within 200 m of pickup, Passenger shows **1 min away**.
- If no fresh eligible driver is available, Passenger shows **No nearby driver online** instead of a fabricated ETA.
- This build still has one development driver identity; multi-driver/category eligibility comes in the larger dispatch architecture.

## Testing

1. Start the shared backend.
2. Open Driver v0.5.1, grant location permission, and go online.
3. Keep Driver open so its current foreground location continues publishing.
4. In Passenger v0.22.2, choose a destination and open Booking summary.
5. The category ETA should update within about 5 seconds. If both phones are at the same location it should settle at **1 min away**.
6. Move the driver phone and verify the pickup ETA changes after new location updates.

Background location remains planned for Driver v0.6 / Build 23.
