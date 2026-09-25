package com.ridenova.passenger.data

import android.content.Context
import com.ridenova.passenger.model.*
import org.json.JSONArray
import org.json.JSONObject

/**
 * Small on-device persistence layer for the prototype.
 * Production account/trip state will move to the RideNova backend, while this store
 * remains useful for local settings/cache and offline-friendly UI state.
 */
class RideNovaLocalStore(context: Context) {
    private val prefs = context.getSharedPreferences("ridenova_local_state", Context.MODE_PRIVATE)

    fun isOnboardingComplete(): Boolean = prefs.getBoolean(KEY_ONBOARDING_COMPLETE, false)

    fun loadProfile(): RiderProfile? {
        val raw = prefs.getString(KEY_PROFILE, null) ?: return null
        return runCatching {
            val json = JSONObject(raw)
            RiderProfile(
                firstName = json.optString("firstName"),
                lastName = json.optString("lastName"),
                email = json.optString("email"),
                phone = json.optString("phone")
            )
        }.getOrNull()
    }

    fun saveProfile(profile: RiderProfile) {
        val json = JSONObject()
            .put("firstName", profile.firstName)
            .put("lastName", profile.lastName)
            .put("email", profile.email)
            .put("phone", profile.phone)
        prefs.edit()
            .putString(KEY_PROFILE, json.toString())
            .putBoolean(KEY_ONBOARDING_COMPLETE, true)
            .apply()
    }



    fun loadSavedPlace(slot: String): PlaceSuggestion? {
        val raw = prefs.getString(KEY_SAVED_PLACE_PREFIX + slot.lowercase(), null) ?: return null
        return runCatching { placeFromJson(JSONObject(raw)) }.getOrNull()
    }

    fun saveSavedPlace(slot: String, place: PlaceSuggestion) {
        prefs.edit().putString(KEY_SAVED_PLACE_PREFIX + slot.lowercase(), placeToJson(place).toString()).apply()
    }

    fun clearSavedPlace(slot: String) {
        prefs.edit().remove(KEY_SAVED_PLACE_PREFIX + slot.lowercase()).apply()
    }

    fun loadRecentDestinations(): List<PlaceSuggestion> {
        val raw = prefs.getString(KEY_RECENT_DESTINATIONS, null) ?: return emptyList()
        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) add(placeFromJson(array.getJSONObject(i)))
            }
        }.getOrDefault(emptyList())
    }

    fun addRecentDestination(place: PlaceSuggestion): List<PlaceSuggestion> {
        val current = loadRecentDestinations()
        val identity = destinationIdentity(place)
        val updated = buildList {
            add(place)
            current.filterNot { destinationIdentity(it) == identity }.forEach { add(it) }
        }.take(MAX_RECENT_DESTINATIONS)
        saveRecentDestinations(updated)
        return updated
    }

    fun removeRecentDestination(place: PlaceSuggestion): List<PlaceSuggestion> {
        val identity = destinationIdentity(place)
        val updated = loadRecentDestinations().filterNot { destinationIdentity(it) == identity }
        saveRecentDestinations(updated)
        return updated
    }

    fun clearRecentDestinations() {
        prefs.edit().remove(KEY_RECENT_DESTINATIONS).apply()
    }

    fun replaceRecentDestinations(destinations: List<PlaceSuggestion>) {
        saveRecentDestinations(destinations)
    }

    fun clearPassengerData() {
        prefs.edit()
            .remove(KEY_PROFILE)
            .remove(KEY_ONBOARDING_COMPLETE)
            .remove(KEY_TRIPS)
            .remove(KEY_RECENT_DESTINATIONS)
            .remove(KEY_SAVED_PLACE_PREFIX + "home")
            .remove(KEY_SAVED_PLACE_PREFIX + "work")
            .apply()
    }

    private fun saveRecentDestinations(destinations: List<PlaceSuggestion>) {
        val array = JSONArray()
        destinations.take(MAX_RECENT_DESTINATIONS).forEach { array.put(placeToJson(it)) }
        prefs.edit().putString(KEY_RECENT_DESTINATIONS, array.toString()).apply()
    }

    private fun destinationIdentity(place: PlaceSuggestion): String =
        place.placeId?.takeIf { it.isNotBlank() } ?: place.address.trim().lowercase()

    fun loadTrips(): List<RideTrip> {
        val raw = prefs.getString(KEY_TRIPS, null) ?: return emptyList()
        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    tripFromJson(array.getJSONObject(i))?.let(::add)
                }
            }
        }.getOrDefault(emptyList())
    }

    fun saveTrips(trips: List<RideTrip>) {
        val array = JSONArray()
        trips.take(MAX_STORED_TRIPS).forEach { array.put(tripToJson(it)) }
        prefs.edit().putString(KEY_TRIPS, array.toString()).apply()
    }

    private fun tripToJson(trip: RideTrip): JSONObject = JSONObject().apply {
        put("id", trip.id)
        put("draft", draftToJson(trip.draft))
        put("option", optionToJson(trip.option))
        put("status", trip.status.name)
        put("requestedAt", trip.requestedAtEpochMs)
        put("updatedAt", trip.updatedAtEpochMs)
        put("graceEndsAt", trip.graceEndsAtEpochMs)
        put("cancelFee", trip.cancellationFeeCad)
        trip.pin?.let { put("pin", it) }
        trip.driver?.let { put("driver", driverToJson(it)) }
        trip.payment?.let { put("payment", paymentToJson(it)) }
    }

    private fun tripFromJson(json: JSONObject): RideTrip? = runCatching {
        RideTrip(
            id = json.getString("id"),
            draft = draftFromJson(json.getJSONObject("draft")),
            option = optionFromJson(json.getJSONObject("option")),
            status = TripStatus.valueOf(json.getString("status")),
            requestedAtEpochMs = json.getLong("requestedAt"),
            updatedAtEpochMs = json.getLong("updatedAt"),
            graceEndsAtEpochMs = json.getLong("graceEndsAt"),
            driver = json.optJSONObject("driver")?.let(::driverFromJson),
            pin = json.optString("pin").takeIf { it.isNotBlank() },
            cancellationFeeCad = json.optDouble("cancelFee", 0.0),
            payment = json.optJSONObject("payment")?.let(::paymentFromJson)
        )
    }.getOrNull()

    private fun draftToJson(draft: BookingDraft): JSONObject = JSONObject().apply {
        put("pickup", placeToJson(draft.pickup))
        draft.destination?.let { put("destination", placeToJson(it)) }
        put("tier", draft.selectedTier.name)
        draft.routeEstimate?.let { put("route", routeToJson(it)) }
        put("scheduled", draft.scheduled)
        put("scheduleLabel", draft.scheduleLabel)
        draft.scheduledAtEpochMs?.let { put("scheduledAtEpochMs", it) }
        draft.scheduleTimeZone?.let { put("scheduleTimeZone", it) }
    }

    private fun draftFromJson(json: JSONObject): BookingDraft = BookingDraft(
        pickup = placeFromJson(json.getJSONObject("pickup")),
        destination = json.optJSONObject("destination")?.let(::placeFromJson),
        selectedTier = runCatching { RideTier.valueOf(json.optString("tier", RideTier.ECONOMY.name)) }.getOrDefault(RideTier.ECONOMY),
        routeEstimate = json.optJSONObject("route")?.let(::routeFromJson),
        scheduled = json.optBoolean("scheduled", false),
        scheduleLabel = if (json.has("scheduledAtEpochMs")) ScheduleTime.label(json.getLong("scheduledAtEpochMs"), java.util.TimeZone.getDefault().id) else json.optString("scheduleLabel", "Now"),
        scheduledAtEpochMs = if (json.has("scheduledAtEpochMs")) json.getLong("scheduledAtEpochMs") else null,
        scheduleTimeZone = json.optString("scheduleTimeZone").takeIf { it.isNotBlank() }
    )

    private fun placeToJson(place: PlaceSuggestion): JSONObject = JSONObject().apply {
        put("name", place.name)
        put("address", place.address)
        place.latitude?.let { put("lat", it) }
        place.longitude?.let { put("lng", it) }
        place.placeId?.let { put("placeId", it) }
    }

    private fun placeFromJson(json: JSONObject): PlaceSuggestion = PlaceSuggestion(
        name = json.optString("name"),
        address = json.optString("address"),
        latitude = if (json.has("lat")) json.optDouble("lat") else null,
        longitude = if (json.has("lng")) json.optDouble("lng") else null,
        placeId = json.optString("placeId").takeIf { it.isNotBlank() }
    )

    private fun routeToJson(route: RouteEstimate): JSONObject = JSONObject().apply {
        put("distanceKm", route.distanceKm)
        put("durationMinutes", route.durationMinutes)
        put("isApproximate", route.isApproximate)
        put("routeType", route.routeType.name)
        val points = JSONArray()
        route.path.forEach { point ->
            points.put(JSONObject().put("lat", point.latitude).put("lng", point.longitude))
        }
        put("path", points)
    }

    private fun routeFromJson(json: JSONObject): RouteEstimate {
        val pointsJson = json.optJSONArray("path") ?: JSONArray()
        val points = buildList {
            for (i in 0 until pointsJson.length()) {
                val point = pointsJson.getJSONObject(i)
                add(RoutePoint(point.getDouble("lat"), point.getDouble("lng")))
            }
        }
        return RouteEstimate(
            distanceKm = json.optDouble("distanceKm", 0.0),
            durationMinutes = json.optInt("durationMinutes", 0),
            isApproximate = json.optBoolean("isApproximate", false),
            path = points,
            routeType = runCatching { RouteType.valueOf(json.optString("routeType", RouteType.FASTEST.name)) }.getOrDefault(RouteType.FASTEST)
        )
    }

    private fun optionToJson(option: RideOption): JSONObject = JSONObject()
        .put("tier", option.tier.name)
        .put("title", option.title)
        .put("description", option.description)
        .put("etaMinutes", option.etaMinutes)
        .put("fareCad", option.fareCad)
        .put("seats", option.seats)

    private fun optionFromJson(json: JSONObject): RideOption = RideOption(
        tier = RideTier.valueOf(json.getString("tier")),
        title = json.getString("title"),
        description = json.getString("description"),
        etaMinutes = json.getInt("etaMinutes"),
        fareCad = json.getDouble("fareCad"),
        seats = json.getInt("seats")
    )

    private fun driverToJson(driver: DriverProfile): JSONObject = JSONObject()
        .put("name", driver.name)
        .put("rating", driver.rating)
        .put("vehicle", driver.vehicle)
        .put("colour", driver.colour)
        .put("plate", driver.plate)
        .put("pickupEtaMinutes", driver.pickupEtaMinutes)

    private fun driverFromJson(json: JSONObject): DriverProfile = DriverProfile(
        name = json.getString("name"),
        rating = json.getDouble("rating"),
        vehicle = json.getString("vehicle"),
        colour = json.getString("colour"),
        plate = json.getString("plate"),
        pickupEtaMinutes = json.getInt("pickupEtaMinutes")
    )

    private fun paymentToJson(payment: TripPayment): JSONObject = JSONObject()
        .put("methodId", payment.methodId)
        .put("type", payment.type)
        .put("brand", payment.brand)
        .put("last4", payment.last4)
        .put("status", payment.status.name)
        .put("amountCents", payment.amountCents)
        .put("developmentOnly", payment.developmentOnly)

    private fun paymentFromJson(json: JSONObject): TripPayment = TripPayment(
        methodId = json.optString("methodId"),
        type = json.optString("type", "CARD"),
        brand = json.optString("brand", "Development card"),
        last4 = json.optString("last4", "4242"),
        status = runCatching { PaymentStatus.valueOf(json.optString("status", "NOT_CHARGED")) }
            .getOrDefault(PaymentStatus.NOT_CHARGED),
        amountCents = json.optLong("amountCents", 0),
        developmentOnly = json.optBoolean("developmentOnly", true)
    )

    private companion object {
        const val KEY_ONBOARDING_COMPLETE = "onboarding_complete"
        const val KEY_PROFILE = "rider_profile"
        const val KEY_TRIPS = "trips"
        const val KEY_RECENT_DESTINATIONS = "recent_destinations"
        const val KEY_SAVED_PLACE_PREFIX = "saved_place_"
        const val MAX_STORED_TRIPS = 30
        const val MAX_RECENT_DESTINATIONS = 8
    }
}
