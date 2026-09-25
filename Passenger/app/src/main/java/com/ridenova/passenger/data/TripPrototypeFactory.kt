package com.ridenova.passenger.data

import com.ridenova.passenger.model.BookingDraft
import com.ridenova.passenger.model.DriverProfile
import com.ridenova.passenger.model.RideTrip
import com.ridenova.passenger.model.TripStatus

/**
 * Local-only trip creation for the v0.8 passenger prototype.
 * The production backend will create authoritative trip IDs, driver assignments,
 * cancellation decisions, timestamps, fares and state transitions.
 */
object TripPrototypeFactory {
    val demoDriver = DriverProfile(
        name = "Alex",
        rating = 4.96,
        vehicle = "Toyota RAV4",
        colour = "Midnight blue",
        plate = "RNV 204",
        pickupEtaMinutes = 4
    )

    fun create(draft: BookingDraft): RideTrip {
        val route = draft.routeEstimate ?: FareEstimator.route(draft.pickup, draft.destination)
        val option = FareEstimator.rideOptions(route).first { it.tier == draft.selectedTier }
        val now = System.currentTimeMillis()
        val status = if (draft.scheduled) TripStatus.SCHEDULED else TripStatus.SEARCHING
        val shortId = now.toString().takeLast(6)

        return RideTrip(
            id = "RN-$shortId",
            draft = draft.copy(routeEstimate = route),
            option = option,
            status = status,
            requestedAtEpochMs = now,
            updatedAtEpochMs = now,
            graceEndsAtEpochMs = now + 120_000L
        )
    }
}
