package com.ridenova.driver.data

import android.content.Context
import com.google.android.gms.maps.model.LatLng
import com.ridenova.driver.model.DriverAvailability
import com.ridenova.driver.model.RideRequest
import com.ridenova.driver.model.RideStage
import com.ridenova.driver.model.Rider
import org.json.JSONObject

data class RestoredDriverSession(
    val availability: DriverAvailability,
    val stage: RideStage,
    val ride: RideRequest?
)

/** Keeps an accepted demo ride through process death. Pending offers are never restored. */
class DriverSessionStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("driver_demo_session", Context.MODE_PRIVATE)

    fun save(availability: DriverAvailability, stage: RideStage, ride: RideRequest?) {
        val storedStage = if (stage == RideStage.REQUESTED) RideStage.IDLE else stage
        val json = JSONObject().put("availability", availability.name).put("stage", storedStage.name)
        if (storedStage != RideStage.IDLE && ride != null) json.put("ride", rideToJson(ride))
        // This small write must finish before Android can terminate the activity.
        prefs.edit().putString("session", json.toString()).commit()
    }

    fun restore(): RestoredDriverSession = runCatching {
        val json = JSONObject(prefs.getString("session", "{}") ?: "{}")
        val availability = DriverAvailability.valueOf(json.optString("availability", "OFFLINE"))
        val stage = RideStage.valueOf(json.optString("stage", "IDLE"))
        val ride = json.optJSONObject("ride")?.let(::rideFromJson)
        RestoredDriverSession(availability, if (ride == null) RideStage.IDLE else stage, ride)
    }.getOrDefault(RestoredDriverSession(DriverAvailability.OFFLINE, RideStage.IDLE, null))

    private fun pointJson(point: LatLng) = JSONObject().put("latitude", point.latitude).put("longitude", point.longitude)
    private fun point(json: JSONObject) = LatLng(json.getDouble("latitude"), json.getDouble("longitude"))

    private fun rideToJson(ride: RideRequest) = JSONObject()
        .put("id", ride.id).put("riderId", ride.rider.id).put("riderName", ride.rider.name)
        .put("riderRating", ride.rider.rating).put("riderTrips", ride.rider.trips)
        .put("pickupName", ride.pickupName).put("pickup", pointJson(ride.pickup))
        .put("destinationName", ride.destinationName).put("destination", pointJson(ride.destination))
        .put("pickupDistanceKm", ride.pickupDistanceKm).put("pickupEtaMin", ride.pickupEtaMin)
        .put("tripDistanceKm", ride.tripDistanceKm).put("tripEtaMin", ride.tripEtaMin)
        .put("fareCad", ride.fareCad).put("driverEstimatedEarningsCad", ride.driverEstimatedEarningsCad)
        .put("category", ride.category)

    private fun rideFromJson(json: JSONObject) = RideRequest(
        id = json.getString("id"),
        rider = Rider(json.getString("riderId"), json.getString("riderName"),
            json.getDouble("riderRating"), json.getInt("riderTrips")),
        pickupName = json.getString("pickupName"), pickup = point(json.getJSONObject("pickup")),
        destinationName = json.getString("destinationName"), destination = point(json.getJSONObject("destination")),
        pickupDistanceKm = json.getDouble("pickupDistanceKm"), pickupEtaMin = json.getInt("pickupEtaMin"),
        tripDistanceKm = json.getDouble("tripDistanceKm"), tripEtaMin = json.getInt("tripEtaMin"),
        fareCad = json.getDouble("fareCad"), driverEstimatedEarningsCad = json.getDouble("driverEstimatedEarningsCad"),
        category = json.optString("category", "Economy")
    )
}
