package com.ridenova.passenger.data

import com.ridenova.passenger.model.PlaceSuggestion
import com.ridenova.passenger.model.RideOption
import com.ridenova.passenger.model.RideTier
import com.ridenova.passenger.model.RouteEstimate
import kotlin.math.*

/**
 * v0.5 client-side estimator used only to make the prototype functional.
 * Production RideNova pricing and routing must be returned by the backend.
 */
object FareEstimator {
    private const val EARTH_RADIUS_KM = 6371.0
    private const val ROAD_FACTOR = 1.22

    fun route(pickup: PlaceSuggestion, destination: PlaceSuggestion?): RouteEstimate? {
        val pLat = pickup.latitude ?: return null
        val pLng = pickup.longitude ?: return null
        val dLat = destination?.latitude ?: return null
        val dLng = destination.longitude ?: return null

        val straightKm = haversineKm(pLat, pLng, dLat, dLng)
        val roadKm = max(0.8, straightKm * ROAD_FACTOR)
        // This is only an emergency prototype fallback when Google routing is unavailable. Longer
        // Metro Vancouver trips spend more time on arterials/highways than a flat 32 km/h city
        // assumption allowed for, which produced unrealistically high ETAs (for example ~71 min
        // for a trip Google Maps estimated around 40 min). It remains marked approximate.
        val assumedSpeedKmh = when {
            roadKm >= 20.0 -> 50.0
            roadKm >= 10.0 -> 44.0
            roadKm >= 5.0 -> 38.0
            else -> 30.0
        }
        val minutes = max(4, ceil((roadKm / assumedSpeedKmh) * 60.0 + 3.0).toInt())
        return RouteEstimate(distanceKm = roadKm, durationMinutes = minutes, isApproximate = true)
    }

    fun rideOptions(route: RouteEstimate?): List<RideOption> {
        if (route == null) return DemoData.rideOptions

        return listOf(
            option(RideTier.ECONOMY, "Economy", "Affordable everyday rides", 3, 4, route, 3.25, 1.05, 0.32, 8.50),
            option(RideTier.COMFORT, "Comfort", "Newer, roomier vehicles", 5, 4, route, 5.00, 1.35, 0.38, 11.00),
            option(RideTier.XL, "XL", "Up to 6 passengers", 7, 6, route, 6.50, 1.75, 0.45, 14.00)
        )
    }

    private fun option(
        tier: RideTier,
        title: String,
        description: String,
        pickupEta: Int,
        seats: Int,
        route: RouteEstimate,
        base: Double,
        perKm: Double,
        perMinute: Double,
        minimum: Double
    ): RideOption {
        val bookingFee = 2.50
        val raw = base + route.distanceKm * perKm + route.durationMinutes * perMinute + bookingFee
        val fare = max(minimum, raw)
        return RideOption(tier, title, description, pickupEta, roundMoney(fare), seats)
    }

    private fun roundMoney(value: Double): Double = round(value * 100.0) / 100.0

    private fun haversineKm(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val dLat = Math.toRadians(lat2 - lat1)
        val dLon = Math.toRadians(lon2 - lon1)
        val a = sin(dLat / 2).pow(2) +
            cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) * sin(dLon / 2).pow(2)
        return EARTH_RADIUS_KM * 2 * atan2(sqrt(a), sqrt(1 - a))
    }
}
