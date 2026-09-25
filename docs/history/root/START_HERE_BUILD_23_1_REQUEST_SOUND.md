# RideNova Build 23.1 — Driver Request Sound

## Versions
- Passenger: v0.23 (unchanged from Build 23 Major)
- Driver: v0.6.1
- Shared backend: Build 23 (unchanged)

## Added
Driver v0.6.1 now includes the selected **Nova RiseWarm B (Layered)** ride-request sound.

Behavior:
- Starts when a new ride request first appears.
- Loops while that offer remains active.
- Does not restart on every backend polling refresh for the same ride ID.
- Stops immediately when the driver accepts or declines.
- Stops when the server removes/expires the offer.
- Stops when the driver goes offline.
- Releases audio resources when the Driver ViewModel is destroyed.

The WAV resource is stored at:
`app/src/main/res/raw/nova_ride_request.wav`

## First test
1. Start the shared backend normally.
2. Open Passenger v0.23 and Driver v0.6.1.
3. Put Driver online.
4. Request a ride from Passenger.
5. Confirm the selected tone begins when the request card appears and repeats while the request is waiting.
6. Accept the request and confirm the sound stops immediately.
7. Repeat and test Decline and request expiry as well.

The tone is original RideNova audio and is not a copy of Uber/Lyft notification audio.
