package com.ridenova.driver.model

import com.google.android.gms.maps.model.LatLng

enum class DriverAvailability { OFFLINE, ONLINE }

enum class RideStage {
    IDLE,
    REQUESTED,
    ACCEPTED,
    ARRIVING,
    ARRIVED,
    ON_TRIP,
    COMPLETED
}

data class Rider(
    val id: String,
    val name: String,
    val rating: Double,
    val trips: Int
)

data class RideRequest(
    val id: String,
    val rider: Rider,
    val pickupName: String,
    val pickup: LatLng,
    val destinationName: String,
    val destination: LatLng,
    val pickupDistanceKm: Double,
    val pickupEtaMin: Int,
    val tripDistanceKm: Double,
    val tripEtaMin: Int,
    val fareCad: Double,
    val driverEstimatedEarningsCad: Double,
    val category: String = "Economy",
    val expiresAtEpochMs: Long = 0L,
    val offerMode: String = "EXCLUSIVE",
    val nearbyDriverCount: Int = 1
)

data class CompletedTrip(
    val id: String,
    val pickup: String,
    val destination: String,
    val completedAt: String,
    val grossFareCad: Double,
    val driverEarningsCad: Double,
    val distanceKm: Double,
    val durationMin: Int,
    val completedAtEpochMs: Long = System.currentTimeMillis(),
    val pickupPoint: LatLng? = null,
    val destinationPoint: LatLng? = null,
    val routePoints: List<LatLng> = emptyList(),
    val category: String = ""
)

data class DriverProfile(
    val name: String = "Driver",
    val rating: Double = 0.0,
    val vehicle: String = "Add your vehicle",
    val plate: String = "Not set",
    val totalTrips: Int = 0
)


data class DriverServerStatus(
    val online: Boolean,
    val profile: DriverProfile,
    val activeRideId: String? = null,
    val activeRideStatus: String? = null,
    val lastLocation: LatLng? = null,
    val locationAgeSeconds: Int? = null,
    val dispatchReason: String = "UNKNOWN",
    val category: String = ""
)
