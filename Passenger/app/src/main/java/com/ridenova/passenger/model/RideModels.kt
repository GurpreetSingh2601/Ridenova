package com.ridenova.passenger.model

enum class RideTier { ECONOMY, COMFORT, XL }

data class RiderProfile(
    val firstName: String,
    val lastName: String,
    val email: String = "",
    val phone: String = ""
) {
    val displayName: String get() = listOf(firstName, lastName).filter { it.isNotBlank() }.joinToString(" ")
}

enum class RouteType { BEST, FASTEST, SHORTEST, POCKET, ALTERNATIVE }

enum class TripStatus {
    SCHEDULED,
    SEARCHING,
    DRIVER_ASSIGNED,
    DRIVER_ARRIVED,
    TRIP_STARTED,
    COMPLETED,
    CANCELLED_BY_RIDER,
    SCHEDULE_EXPIRED
}

data class RideOption(
    val tier: RideTier,
    val title: String,
    val description: String,
    val etaMinutes: Int,
    val fareCad: Double,
    val seats: Int,
    val breakdown: FareBreakdown? = null
)

data class FareBreakdown(val subtotalCents: Long, val gstCents: Long, val totalCents: Long)

data class DriverAvailability(
    val available: Boolean,
    val etaMinutes: Int? = null,
    val distanceKm: Double? = null,
    val locationAgeSeconds: Int? = null
)

data class PlaceSuggestion(
    val name: String,
    val address: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val placeId: String? = null
)

data class PaymentMethod(
    val id: String,
    val type: String = "CARD",
    val brand: String,
    val last4: String,
    val expiryMonth: Int,
    val expiryYear: Int,
    val isDefault: Boolean = false,
    val developmentOnly: Boolean = true
) {
    val displayLabel: String get() = "$brand •••• $last4"
}

enum class PaymentStatus { NOT_CHARGED, AUTHORIZED_DEMO, CAPTURED_DEMO, VOIDED }

data class TripPayment(
    val methodId: String,
    val type: String,
    val brand: String,
    val last4: String,
    val status: PaymentStatus,
    val amountCents: Long = 0,
    val developmentOnly: Boolean = true
) {
    val methodLabel: String get() = "$brand •••• $last4"
}

data class RoutePoint(
    val latitude: Double,
    val longitude: Double
)

/** Latest GPS position reported by the connected development Driver app. */
data class DriverPosition(val latitude: Double, val longitude: Double, val recordedAtEpochMs: Long)

data class LiveTripProgress(
    val remainingDistanceKm: Double,
    val remainingEtaMinutes: Int,
    val progress: Double,
    val updatedAtEpochMs: Long
)

data class RouteEstimate(
    val distanceKm: Double,
    val durationMinutes: Int,
    val isApproximate: Boolean = true,
    val path: List<RoutePoint> = emptyList(),
    val routeType: RouteType = RouteType.FASTEST
)

data class RouteChoices(
    val fastest: RouteEstimate,
    val shortest: RouteEstimate? = null,
    val alternatives: List<RouteEstimate> = emptyList(),
    val best: RouteEstimate? = null,
    val pocketFriendly: RouteEstimate? = null
)

data class BookingDraft(
    val pickup: PlaceSuggestion = PlaceSuggestion("Current location", "British Columbia"),
    val destination: PlaceSuggestion? = null,
    val selectedTier: RideTier = RideTier.ECONOMY,
    val routeEstimate: RouteEstimate? = null,
    val scheduled: Boolean = false,
    val scheduleLabel: String = "Now",
    val scheduledAtEpochMs: Long? = null,
    val scheduleTimeZone: String? = null
)

data class DriverProfile(
    val name: String,
    val rating: Double,
    val vehicle: String,
    val colour: String,
    val plate: String,
    val pickupEtaMinutes: Int
)

data class RideTrip(
    val id: String,
    val draft: BookingDraft,
    val option: RideOption,
    val status: TripStatus,
    val requestedAtEpochMs: Long,
    val updatedAtEpochMs: Long,
    val graceEndsAtEpochMs: Long,
    val driver: DriverProfile? = null,
    val pin: String? = null,
    val cancellationFeeCad: Double = 0.0,
    val cancellationFeeAfterGraceCad: Double = 5.0,
    val payment: TripPayment? = null,
    val driverPosition: DriverPosition? = null,
    val liveTrip: LiveTripProgress? = null
)
