package com.ridenova.passenger.data

import com.ridenova.passenger.model.*

/**
 * Boundary the Android app will use when the RideNova backend is connected.
 * Build 40 uses this contract for backend-authoritative quotes, rides and recovery.
 */
interface RideNovaApiContract {
    suspend fun quoteRide(request: QuoteRequest): QuoteResponse
    suspend fun requestRide(request: CreateRideRequest): RideTrip
    suspend fun cancelRide(tripId: String): RideTrip
    suspend fun getTrip(tripId: String): RideTrip
    suspend fun listTrips(): List<RideTrip>
}

data class QuoteRequest(
    val pickup: PlaceSuggestion,
    val destination: PlaceSuggestion,
    val route: RouteEstimate,
    val scheduled: Boolean,
    val scheduleLabel: String,
    val scheduledAtEpochMs: Long? = null,
    val scheduleTimeZone: String? = null
)

data class QuoteResponse(
    val options: List<RideOption>,
    val currency: String = "CAD",
    val expiresAtEpochMs: Long,
    val quoteToken: String? = null,
    val serverRoute: RouteEstimate? = null,
    val routeChanged: Boolean = false,
    val routeChangeReason: String? = null
)

data class CreateRideRequest(
    val draft: BookingDraft,
    val quotedOption: RideOption,
    val quoteToken: String? = null,
    val paymentMethodId: String? = null
)
