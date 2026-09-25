package com.ridenova.driver.data

import com.google.android.gms.maps.model.LatLng

/** Server-owned driver operations. Never derive fares or assign riders on the device. */
interface DriverApiContract {
    suspend fun setAvailability(online: Boolean)
    suspend fun currentOffer(): DriverOffer?
    suspend fun accept(rideId: String): DriverRideSnapshot
    suspend fun decline(rideId: String)
    suspend fun arrive(rideId: String): DriverRideSnapshot
    suspend fun start(rideId: String): DriverRideSnapshot
    suspend fun complete(rideId: String): DriverRideSnapshot
    suspend fun publishLocation(rideId: String, position: LatLng, recordedAtEpochMs: Long)
    suspend fun activeRide(): DriverRideSnapshot?
}

data class DriverOffer(
    val id: String,
    val pickup: LatLng,
    val destination: LatLng,
    val expiresAtEpochMs: Long
)

data class DriverRideSnapshot(
    val id: String,
    val status: String,
    val updatedAtEpochMs: Long
) {
    init {
        require(status in PASSENGER_VISIBLE_STATUSES) { "Unknown ride status: $status" }
    }
}

/** Values shared with RideNova Passenger's RideTrip.status wire representation. */
val PASSENGER_VISIBLE_STATUSES = setOf(
    "SCHEDULED", "SEARCHING", "DRIVER_ASSIGNED", "DRIVER_ARRIVED",
    "TRIP_STARTED", "COMPLETED", "CANCELLED_BY_RIDER"
)
