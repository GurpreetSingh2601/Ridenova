package com.ridenova.driver.data

import android.content.Context
import com.google.android.gms.maps.model.LatLng
import com.ridenova.driver.model.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject
import java.text.DateFormat
import java.util.Date

/** Foreground UI polling; DriverLocationService independently handles background alerts. */
class RemoteDriverRepository(context: Context, url: String, token: String, private val fleet: Boolean = false) : DriverRepository {
    private val api = DriverHttpApi(url, token, fleet)
    private val history = DemoDriverRepository(context)
    private val _incoming = MutableStateFlow<RideRequest?>(null)
    override val incomingRide: StateFlow<RideRequest?> = _incoming.asStateFlow()
    override val completedTrips = history.completedTrips
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    override suspend fun requestNextRide() {
        while (true) {
            try {
                val json = api.json("GET", "v1/driver/requests/current")
                _incoming.value = if (json.length() > 0) offer(json) else null
                _error.value = null
            } catch (ex: CancellationException) {
                // Cancelling the polling job is a normal lifecycle event (accept/decline/offline/restart).
                // Never surface coroutine cancellation as a server error to the driver.
                throw ex
            } catch (ex: Exception) {
                _error.value = ex.localizedMessage ?: "Cannot reach the development server"
            }
            delay(2_000)
        }
    }

    override suspend fun clearIncomingRide() { _incoming.value = null }
    override suspend fun saveCompletedRide(ride: RideRequest) { history.saveCompletedRide(ride) }

    suspend fun setOnline(online: Boolean, profile: DriverProfile) {
        api.json("POST", "v1/driver/availability", JSONObject().put("online", online)
            .put("name", profile.name).put("vehicle", profile.vehicle).put("plate", profile.plate))
    }

    suspend fun updateProfile(profile: DriverProfile, online: Boolean) {
        if (fleet) api.json("POST", "v2/fleet/driver/profile", JSONObject()
            .put("name", profile.name).put("vehicle", profile.vehicle).put("plate", profile.plate))
        else setOnline(online, profile)
    }

    suspend fun refreshCompletedTrips() {
        val json = api.json("GET", "v1/driver/trips")
        val array = json.optJSONArray("trips") ?: return
        val trips = (0 until array.length()).map { index ->
            val item = array.getJSONObject(index)
            val timestamp = item.optLong("completedAtEpochMs", 0L)
            CompletedTrip(
                id = item.optString("id"),
                pickup = item.optString("pickup", "Pickup"),
                destination = item.optString("destination", "Destination"),
                completedAt = DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(Date(timestamp)),
                grossFareCad = item.optDouble("grossFareCad", 0.0),
                driverEarningsCad = item.optDouble("driverEarningsCad", 0.0),
                distanceKm = item.optDouble("distanceKm", 0.0),
                durationMin = item.optInt("durationMin", 0),
                completedAtEpochMs = timestamp,
                pickupPoint = item.optJSONObject("pickupPoint")?.takeIf { it.has("latitude") }?.let(::point),
                destinationPoint = item.optJSONObject("destinationPoint")?.takeIf { it.has("latitude") }?.let(::point),
                routePoints = item.optJSONArray("routePoints")?.let { array ->
                    (0 until array.length()).mapNotNull { i -> array.optJSONObject(i)?.let(::flexPoint) }
                }.orEmpty(),
                category = item.optString("category")
            )
        }
        history.replaceCompletedTrips(trips)
    }

    suspend fun serverStatus(): DriverServerStatus {
        val json = api.json("GET", "v1/driver/status")
        val location = json.optJSONObject("lastLocation")
        return DriverServerStatus(
            online = json.optBoolean("online", false),
            profile = DriverProfile(
                name = json.optString("name", "Driver"),
                rating = json.optDouble("serviceRating", 0.0),
                vehicle = json.optString("vehicle", "Add your vehicle"),
                plate = json.optString("plate", "Not set")
            ),
            activeRideId = json.optString("activeRideId").takeIf { it.isNotBlank() && it != "null" },
            activeRideStatus = json.optString("activeRideStatus").takeIf { it.isNotBlank() && it != "null" },
            lastLocation = location?.let(::point),
            locationAgeSeconds = location?.optInt("ageSeconds"),
            dispatchReason = json.optString("dispatchReason", "UNKNOWN"),
            category = json.optString("category", "")
        )
    }

    suspend fun action(rideId: String, action: String, pin: String? = null): String {
        require(action in setOf("accept", "decline", "arrive", "start", "complete", "cancel"))
        require(rideId.matches(Regex("[A-Za-z0-9_-]+")))
        val json = api.json("POST", "v1/driver/rides/$rideId/$action",
            JSONObject().apply { pin?.let { put("pin", it) } })
        return json.optString("status")
    }

    suspend fun restoreActive(): Pair<RideRequest, RideStage>? {
        val json = api.json("GET", "v1/driver/rides/active")
        if (json.length() == 0) return null
        val stage = when (json.getString("status")) {
            "DRIVER_ASSIGNED" -> RideStage.ARRIVING
            "DRIVER_ARRIVED" -> RideStage.ARRIVED
            "TRIP_STARTED" -> RideStage.ON_TRIP
            else -> return null
        }
        val draft = json.getJSONObject("draft")
        val option = json.getJSONObject("option")
        val pickup = draft.getJSONObject("pickup")
        val destination = draft.getJSONObject("destination")
        return request(json.getString("id"), pickup, destination, option,
            draft.optJSONObject("routeEstimate")) to stage
    }

    suspend fun publishPresence(point: LatLng) {
        api.json("POST", "v1/driver/location", JSONObject()
            .put("latitude", point.latitude).put("longitude", point.longitude)
            .put("recordedAtEpochMs", System.currentTimeMillis()))
    }

    suspend fun publish(rideId: String, point: LatLng) {
        require(rideId.matches(Regex("[A-Za-z0-9_-]+")))
        api.json("POST", "v1/driver/rides/$rideId/location", JSONObject()
            .put("latitude", point.latitude).put("longitude", point.longitude)
            .put("recordedAtEpochMs", System.currentTimeMillis()))
    }

    private fun offer(json: JSONObject) = RideRequest(
        id = json.getString("id"), rider = Rider("dev", json.optString("riderName", "Demo rider"), 0.0, 0),
        pickupName = json.optString("pickupName"), pickup = point(json.getJSONObject("pickup")),
        destinationName = json.optString("destinationName"), destination = point(json.getJSONObject("destination")),
        pickupDistanceKm = json.optDouble("pickupDistanceKm", 0.0), pickupEtaMin = json.optInt("pickupEtaMin", 5),
        tripDistanceKm = json.optDouble("tripDistanceKm", 0.0), tripEtaMin = json.optInt("tripEtaMin", 0),
        fareCad = json.optDouble("fareCad", 0.0),
        driverEstimatedEarningsCad = json.optDouble("driverEstimatedEarningsCad", 0.0),
        category = json.optString("category", "Economy"),
        expiresAtEpochMs = json.optLong("expiresAtEpochMs", 0L),
        offerMode = json.optString("offerMode", "EXCLUSIVE"),
        nearbyDriverCount = json.optInt("nearbyDriverCount", 1)
    )

    private fun request(id: String, pickup: JSONObject, destination: JSONObject,
                        option: JSONObject, route: JSONObject?) = RideRequest(
        id = id, rider = Rider("dev", "Demo rider", 0.0, 0),
        pickupName = pickup.optString("name"), pickup = point(pickup),
        destinationName = destination.optString("name"), destination = point(destination),
        pickupDistanceKm = 0.0, pickupEtaMin = 5,
        tripDistanceKm = route?.optDouble("distanceKm") ?: 0.0,
        tripEtaMin = route?.optInt("durationMinutes") ?: 0,
        fareCad = option.optDouble("fareCad", 0.0),
        driverEstimatedEarningsCad = option.optJSONObject("breakdown")
            ?.optDouble("driverGrossBeforeCostsCents", 0.0)?.div(100.0) ?: 0.0,
        category = option.optString("title", "Economy"),
        expiresAtEpochMs = 0L
    )

    private fun point(json: JSONObject) = LatLng(json.getDouble("latitude"), json.getDouble("longitude"))
    private fun flexPoint(json: JSONObject): LatLng? {
        val lat = if (json.has("latitude")) json.optDouble("latitude", Double.NaN) else json.optDouble("lat", Double.NaN)
        val lng = if (json.has("longitude")) json.optDouble("longitude", Double.NaN) else json.optDouble("lng", Double.NaN)
        return if (lat.isFinite() && lng.isFinite()) LatLng(lat, lng) else null
    }
}
