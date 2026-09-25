package com.ridenova.driver.data

import android.content.Context
import com.google.android.gms.maps.model.LatLng
import com.ridenova.driver.model.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject
import java.text.DateFormat
import java.util.Date

interface DriverRepository {
    val incomingRide: StateFlow<RideRequest?>
    val completedTrips: StateFlow<List<CompletedTrip>>
    suspend fun requestNextRide()
    suspend fun clearIncomingRide()
    suspend fun saveCompletedRide(ride: RideRequest)
}

class DemoDriverRepository(context: Context) : DriverRepository {
    private val preferences = context.applicationContext.getSharedPreferences("driver_demo_trips", Context.MODE_PRIVATE)
    private val _incomingRide = MutableStateFlow<RideRequest?>(null)
    override val incomingRide: StateFlow<RideRequest?> = _incomingRide.asStateFlow()

    private val _completedTrips = MutableStateFlow(loadTrips())
    override val completedTrips: StateFlow<List<CompletedTrip>> = _completedTrips.asStateFlow()

    override suspend fun requestNextRide() {
        if (_incomingRide.value != null) return
        delay(900)
        _incomingRide.value = RideRequest(
            id = "RN-${System.currentTimeMillis()}",
            rider = Rider("r-204", "Jordan", 4.91, 82),
            pickupName = "Central City, Surrey",
            pickup = LatLng(49.1897, -122.8490),
            destinationName = "Guildford Town Centre",
            destination = LatLng(49.1908, -122.8039),
            pickupDistanceKm = 2.1,
            pickupEtaMin = 6,
            tripDistanceKm = 5.7,
            tripEtaMin = 14,
            fareCad = 17.40,
            driverEstimatedEarningsCad = 12.18,
            category = "Economy"
        )
    }

    override suspend fun clearIncomingRide() {
        _incomingRide.value = null
    }

    override suspend fun saveCompletedRide(ride: RideRequest) {
        val timestamp = System.currentTimeMillis()
        _completedTrips.value = listOf(
            CompletedTrip(
                id = ride.id,
                pickup = ride.pickupName,
                destination = ride.destinationName,
                completedAt = DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(Date(timestamp)),
                grossFareCad = ride.fareCad,
                driverEarningsCad = ride.driverEstimatedEarningsCad,
                distanceKm = ride.tripDistanceKm,
                durationMin = ride.tripEtaMin,
                completedAtEpochMs = timestamp
            )
        ) + _completedTrips.value
        persistTrips()
        _incomingRide.value = null
    }

    fun replaceCompletedTrips(trips: List<CompletedTrip>) {
        _completedTrips.value = trips.sortedByDescending { it.completedAtEpochMs }
        persistTrips()
    }

    private fun persistTrips() {
        val array = JSONArray()
        _completedTrips.value.forEach { trip ->
            array.put(JSONObject().put("id", trip.id).put("pickup", trip.pickup)
                .put("destination", trip.destination).put("completedAtEpochMs", trip.completedAtEpochMs)
                .put("grossFareCad", trip.grossFareCad).put("driverEarningsCad", trip.driverEarningsCad)
                .put("distanceKm", trip.distanceKm).put("durationMin", trip.durationMin))
        }
        preferences.edit().putString("trips", array.toString()).apply()
    }

    private fun loadTrips(): List<CompletedTrip> = runCatching {
        val array = JSONArray(preferences.getString("trips", "[]"))
        (0 until array.length()).map { index ->
            val json = array.getJSONObject(index)
            val timestamp = json.getLong("completedAtEpochMs")
            CompletedTrip(json.getString("id"), json.getString("pickup"), json.getString("destination"),
                DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(Date(timestamp)),
                json.getDouble("grossFareCad"), json.getDouble("driverEarningsCad"),
                json.getDouble("distanceKm"), json.getInt("durationMin"), timestamp)
        }
    }.getOrDefault(emptyList())
}
