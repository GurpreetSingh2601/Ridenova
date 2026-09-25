package com.ridenova.passenger.data

import com.ridenova.passenger.model.*

/**
 * Repository boundary for moving passenger flows from local prototype logic to the
 * RideNova backend without rewriting the Compose screens.
 */
interface RideNovaRepository {
    suspend fun quote(request: QuoteRequest): QuoteResponse
    suspend fun nearbyDriverAvailability(pickup: PlaceSuggestion, tier: RideTier): DriverAvailability
    suspend fun createRide(request: CreateRideRequest): RideTrip
    suspend fun cancelRide(tripId: String): RideTrip
    suspend fun getRide(tripId: String): RideTrip
    suspend fun listRides(): List<RideTrip>
    suspend fun rideExperience(tripId: String): RideExperience
    suspend fun rateRide(tripId: String, stars: Int, tags: List<String>, comment: String): RideExperience
    suspend fun createSupportCase(tripId: String?, category: String, description: String): SupportCase
}

data class RideRating(val stars: Int, val tags: List<String>, val comment: String)
data class RideExperience(val canRate: Boolean, val rating: RideRating?, val supportCaseCount: Int)
data class SupportCase(val id: String, val status: String, val category: String)

/**
 * Local implementation used while the server is not connected. Server-authoritative
 * pricing, trip IDs, dispatch, cancellation policy and ledger entries will replace it.
 */
class PrototypeRideNovaRepository(
    private val localStore: RideNovaLocalStore
) : RideNovaRepository {
    override suspend fun quote(request: QuoteRequest): QuoteResponse {
        if (request.scheduled) require(request.scheduledAtEpochMs?.let { ScheduleTime.isBookable(it, System.currentTimeMillis()) } == true) { "Choose a pickup 15 minutes to 30 days from now" }
        return QuoteResponse(options = FareEstimator.rideOptions(request.route), expiresAtEpochMs = System.currentTimeMillis() + 120_000L)
    }

    override suspend fun nearbyDriverAvailability(pickup: PlaceSuggestion, tier: RideTier): DriverAvailability =
        DriverAvailability(available = false)

    override suspend fun createRide(request: CreateRideRequest): RideTrip {
        val trip = TripPrototypeFactory.create(request.draft).copy(
            payment = TripPayment(
                methodId = request.paymentMethodId ?: "pm_offline_4242",
                type = "CARD", brand = "Visa", last4 = "4242",
                status = PaymentStatus.NOT_CHARGED
            )
        )
        localStore.saveTrips(listOf(trip) + localStore.loadTrips())
        return trip
    }

    override suspend fun cancelRide(tripId: String): RideTrip {
        val trips = localStore.loadTrips()
        val trip = trips.first { it.id == tripId }
        if (trip.status == TripStatus.CANCELLED_BY_RIDER) return trip
        require(trip.status in setOf(TripStatus.SCHEDULED, TripStatus.SEARCHING, TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_ARRIVED)) { "This ride cannot be cancelled" }
        val fee = if (trip.status == TripStatus.SCHEDULED || System.currentTimeMillis() <= trip.graceEndsAtEpochMs) 0.0 else 5.0
        val updated = trip.copy(
            status = TripStatus.CANCELLED_BY_RIDER,
            updatedAtEpochMs = System.currentTimeMillis(),
            cancellationFeeCad = fee,
            payment = trip.payment?.copy(
                status = if (fee == 0.0) PaymentStatus.VOIDED else PaymentStatus.CAPTURED_DEMO,
                amountCents = (fee * 100).toLong()
            )
        )
        localStore.saveTrips(trips.map { if (it.id == tripId) updated else it })
        return updated
    }

    override suspend fun getRide(tripId: String): RideTrip =
        localStore.loadTrips().first { it.id == tripId }

    override suspend fun listRides(): List<RideTrip> = localStore.loadTrips()

    override suspend fun rideExperience(tripId: String) = RideExperience(true, null, 0)
    override suspend fun rateRide(tripId: String, stars: Int, tags: List<String>, comment: String) =
        RideExperience(true, RideRating(stars, tags, comment), 0)
    override suspend fun createSupportCase(tripId: String?, category: String, description: String) =
        SupportCase("offline-${System.currentTimeMillis()}", "OPEN", category)
}
