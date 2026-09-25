package com.ridenova.passenger.data

import com.ridenova.passenger.model.*
import org.json.JSONArray
import org.json.JSONObject

/**
 * Network-backed repository contract for the RideNova server.
 * Expected endpoints:
 * POST /v1/passenger/quotes
 * POST /v1/passenger/rides
 * POST /v1/passenger/rides/{id}/cancel
 * GET  /v1/passenger/rides/{id}
 * GET  /v1/passenger/rides
 */
class BackendRideNovaRepository(
    private val client: RideNovaHttpClient
) : RideNovaRepository {
    override suspend fun quote(request: QuoteRequest): QuoteResponse {
        val json = JSONObject()
            .put("pickup", placeJson(request.pickup))
            .put("destination", placeJson(request.destination))
            .put("route", routeJson(request.route))
            .put("scheduled", request.scheduled)
            .put("scheduleLabel", request.scheduleLabel)
            .apply {
                request.scheduledAtEpochMs?.let { put("scheduledAtEpochMs", it) }
                request.scheduleTimeZone?.let { put("scheduleTimeZone", it) }
            }
        return when (val result = client.post("v1/passenger/quotes", json)) {
            is ApiResult.Success -> quoteFromJson(result.value)
            is ApiResult.Failure -> error(result.message)
        }
    }

    override suspend fun nearbyDriverAvailability(pickup: PlaceSuggestion, tier: RideTier): DriverAvailability {
        val json = JSONObject()
            .put("pickup", placeJson(pickup))
            .put("tier", tier.name)
        return when (val result = client.post("v1/passenger/availability", json)) {
            is ApiResult.Success -> DriverAvailability(
                available = result.value.optBoolean("available", false),
                etaMinutes = if (result.value.has("etaMinutes") && !result.value.isNull("etaMinutes")) result.value.optInt("etaMinutes") else null,
                distanceKm = if (result.value.has("distanceKm") && !result.value.isNull("distanceKm")) result.value.optDouble("distanceKm") else null,
                locationAgeSeconds = if (result.value.has("locationAgeSeconds") && !result.value.isNull("locationAgeSeconds")) result.value.optInt("locationAgeSeconds") else null
            )
            is ApiResult.Failure -> error(result.message)
        }
    }

    override suspend fun createRide(request: CreateRideRequest): RideTrip {
        val quoteToken = request.quoteToken?.takeIf { it.isNotBlank() }
            ?: error("Please get a current fare before confirming your ride")
        // The quote already stores the authoritative route and fare. Do not resend
        // the draft/polyline here: long road routes exceed the booking body limit.
        val json = JSONObject()
            .put("quoteToken", quoteToken)
            .put("rideOption", JSONObject().put("tier", request.quotedOption.tier.name))
        request.paymentMethodId?.let { json.put("paymentMethodId", it) }
        val first = client.post("v1/passenger/rides", json)
        // A create call is idempotent only because the backend binds one ride to this quote token.
        // Replay once after an ambiguous connection failure; the server returns the same ride if
        // the first request committed before its response was lost.
        val result = if (first is ApiResult.Failure && first.statusCode == null && request.quoteToken != null) {
            client.post("v1/passenger/rides", json)
        } else first
        return when (result) {
            is ApiResult.Success -> tripFromJson(result.value)
            is ApiResult.Failure -> error(result.message)
        }
    }

    override suspend fun cancelRide(tripId: String): RideTrip =
        when (val result = client.post("v1/passenger/rides/$tripId/cancel", JSONObject())) {
            is ApiResult.Success -> tripFromJson(result.value)
            is ApiResult.Failure -> error(result.message)
        }

    override suspend fun getRide(tripId: String): RideTrip =
        when (val result = client.get("v1/passenger/rides/$tripId")) {
            is ApiResult.Success -> tripFromJson(result.value)
            is ApiResult.Failure -> error(result.message)
        }

    override suspend fun listRides(): List<RideTrip> =
        when (val result = client.get("v1/passenger/rides")) {
            is ApiResult.Success -> {
                val array = result.value.optJSONArray("rides") ?: JSONArray()
                buildList { for (i in 0 until array.length()) add(tripFromJson(array.getJSONObject(i))) }
            }
            is ApiResult.Failure -> error(result.message)
        }

    override suspend fun rideExperience(tripId: String): RideExperience =
        when (val result = client.get("v1/passenger/rides/$tripId/experience")) {
            is ApiResult.Success -> experienceFromJson(result.value)
            is ApiResult.Failure -> error(result.message)
        }

    override suspend fun rateRide(tripId: String, stars: Int, tags: List<String>, comment: String): RideExperience {
        val body = JSONObject().put("stars", stars).put("tags", JSONArray(tags)).put("comment", comment)
        return when (val result = client.post("v1/passenger/rides/$tripId/rating", body)) {
            is ApiResult.Success -> experienceFromJson(result.value)
            is ApiResult.Failure -> error(result.message)
        }
    }

    override suspend fun createSupportCase(tripId: String?, category: String, description: String): SupportCase {
        val body = JSONObject().put("category", category).put("description", description)
        tripId?.let { body.put("rideId", it) }
        return when (val result = client.post("v1/passenger/support-cases", body)) {
            is ApiResult.Success -> SupportCase(result.value.getString("id"), result.value.getString("status"), result.value.getString("category"))
            is ApiResult.Failure -> error(result.message)
        }
    }

    private fun experienceFromJson(json: JSONObject): RideExperience {
        val rating = json.optJSONObject("rating")?.let { item ->
            val values = item.optJSONArray("tags") ?: JSONArray()
            RideRating(item.getInt("stars"), (0 until values.length()).map { values.getString(it) }, item.optString("comment"))
        }
        return RideExperience(json.optBoolean("canRate"), rating, json.optInt("supportCaseCount"))
    }

    private fun quoteFromJson(json: JSONObject): QuoteResponse {
        val array = json.optJSONArray("options") ?: error("Quote response has no ride options")
        val options = buildList { for (i in 0 until array.length()) add(optionFromJson(array.getJSONObject(i))) }
        return QuoteResponse(
            options = options,
            currency = json.optString("currency", "CAD"),
            expiresAtEpochMs = json.getLong("expiresAtEpochMs"),
            quoteToken = json.getString("quoteToken"),
            serverRoute = json.optJSONObject("route")?.let(::routeFromJson),
            routeChanged = json.optBoolean("routeChanged", false),
            routeChangeReason = if (json.optBoolean("routeChanged", false)) {
                (json.opt("routeChangeReason") as? String)
                    ?.trim()?.takeIf { it.isNotEmpty() && !it.equals("null", ignoreCase = true) }
                    ?: "The route changed. Please review the updated route and fare before confirming."
            } else null
        )
    }

    private fun tripFromJson(json: JSONObject): RideTrip = RideTrip(
        id = json.getString("id"),
        draft = draftFromJson(json.getJSONObject("draft")),
        option = optionFromJson(json.getJSONObject("option")),
        status = TripStatus.valueOf(json.getString("status")),
        requestedAtEpochMs = json.getLong("requestedAtEpochMs"),
        updatedAtEpochMs = json.getLong("updatedAtEpochMs"),
        graceEndsAtEpochMs = json.getLong("graceEndsAtEpochMs"),
        driver = json.optJSONObject("driver")?.let(::driverFromJson),
        pin = json.optString("pin").takeIf { it.isNotBlank() },
        cancellationFeeCad = json.optDouble("cancellationFeeCad", 0.0),
        cancellationFeeAfterGraceCad = json.getDouble("cancellationFeeAfterGraceCad"),
        payment = json.optJSONObject("payment")?.let(::paymentFromJson),
        driverPosition = json.optJSONObject("driverPosition")?.let { position ->
            DriverPosition(position.getDouble("latitude"), position.getDouble("longitude"), position.getLong("recordedAtEpochMs"))
        },
        liveTrip = json.optJSONObject("liveTrip")?.let { live ->
            LiveTripProgress(
                remainingDistanceKm = live.optDouble("remainingDistanceKm", 0.0),
                remainingEtaMinutes = live.optInt("remainingEtaMinutes", 0),
                progress = live.optDouble("progress", 0.0),
                updatedAtEpochMs = live.optLong("updatedAtEpochMs", 0L)
            )
        }
    )

    private fun placeJson(place: PlaceSuggestion) = JSONObject()
        .put("name", place.name).put("address", place.address)
        .apply {
            place.latitude?.let { put("latitude", it) }
            place.longitude?.let { put("longitude", it) }
            place.placeId?.let { put("placeId", it) }
        }

    private fun routeJson(route: RouteEstimate) = JSONObject()
        .put("distanceKm", route.distanceKm)
        .put("durationMinutes", route.durationMinutes)
        .put("routeType", route.routeType.name)
        .put("isApproximate", route.isApproximate)
        .put("path", JSONArray().apply {
            route.path.forEach { point ->
                put(JSONObject().put("latitude", point.latitude).put("longitude", point.longitude))
            }
        })

    private fun optionJson(option: RideOption) = JSONObject()
        .put("tier", option.tier.name).put("title", option.title)
        .put("description", option.description).put("etaMinutes", option.etaMinutes)
        .put("fareCad", option.fareCad).put("seats", option.seats)

    private fun draftJson(draft: BookingDraft) = JSONObject()
        .put("pickup", placeJson(draft.pickup))
        .apply { draft.destination?.let { put("destination", placeJson(it)) } }
        .put("selectedTier", draft.selectedTier.name)
        .apply { draft.routeEstimate?.let { put("routeEstimate", routeJson(it)) } }
        .put("scheduled", draft.scheduled)
        .put("scheduleLabel", draft.scheduleLabel)
        .apply {
            draft.scheduledAtEpochMs?.let { put("scheduledAtEpochMs", it) }
            draft.scheduleTimeZone?.let { put("scheduleTimeZone", it) }
        }

    private fun placeFromJson(json: JSONObject) = PlaceSuggestion(
        name = json.optString("name"), address = json.optString("address"),
        latitude = if (json.has("latitude")) json.optDouble("latitude") else null,
        longitude = if (json.has("longitude")) json.optDouble("longitude") else null,
        placeId = json.optString("placeId").takeIf { it.isNotBlank() }
    )

    private fun routeFromJson(json: JSONObject): RouteEstimate {
        val path = json.optJSONArray("path") ?: JSONArray()
        val points = buildList {
            for (index in 0 until path.length()) {
                path.optJSONObject(index)?.let { point ->
                    if (point.has("latitude") && point.has("longitude")) {
                        add(RoutePoint(point.getDouble("latitude"), point.getDouble("longitude")))
                    }
                }
            }
        }
        return RouteEstimate(
            distanceKm = json.optDouble("distanceKm"),
            durationMinutes = json.optInt("durationMinutes"),
            isApproximate = json.optBoolean("isApproximate", false),
            path = points,
            routeType = runCatching { RouteType.valueOf(json.optString("routeType", "FASTEST")) }.getOrDefault(RouteType.FASTEST)
        )
    }

    private fun optionFromJson(json: JSONObject) = RideOption(
        tier = RideTier.valueOf(json.getString("tier")),
        title = json.getString("title"), description = json.optString("description"),
        etaMinutes = json.getInt("etaMinutes"), fareCad = json.getDouble("fareCad"), seats = json.getInt("seats"),
        breakdown = json.optJSONObject("breakdown")?.let {
            FareBreakdown(it.getLong("subtotalCents"), it.getLong("gstCents"), it.getLong("totalCents"))
        }
    )

    private fun draftFromJson(json: JSONObject) = BookingDraft(
        pickup = placeFromJson(json.getJSONObject("pickup")),
        destination = json.optJSONObject("destination")?.let(::placeFromJson),
        selectedTier = RideTier.valueOf(json.optString("selectedTier", "ECONOMY")),
        routeEstimate = json.optJSONObject("routeEstimate")?.let(::routeFromJson),
        scheduled = json.optBoolean("scheduled", false),
        scheduleLabel = if (json.has("scheduledAtEpochMs")) ScheduleTime.label(json.getLong("scheduledAtEpochMs"), java.util.TimeZone.getDefault().id) else json.optString("scheduleLabel", "Now"),
        scheduledAtEpochMs = if (json.has("scheduledAtEpochMs")) json.getLong("scheduledAtEpochMs") else null,
        scheduleTimeZone = json.optString("scheduleTimeZone").takeIf { it.isNotBlank() }
    )

    private fun driverFromJson(json: JSONObject) = DriverProfile(
        name = json.getString("name"), rating = json.getDouble("rating"),
        vehicle = json.getString("vehicle"), colour = json.getString("colour"),
        plate = json.getString("plate"), pickupEtaMinutes = json.getInt("pickupEtaMinutes")
    )

    private fun paymentFromJson(json: JSONObject) = TripPayment(
        methodId = json.optString("methodId"), type = json.optString("type", "CARD"),
        brand = json.optString("brand", "Development card"), last4 = json.optString("last4", "4242"),
        status = runCatching { PaymentStatus.valueOf(json.optString("status", "NOT_CHARGED")) }.getOrDefault(PaymentStatus.NOT_CHARGED),
        amountCents = json.optLong("amountCents", 0), developmentOnly = json.optBoolean("developmentOnly", true)
    )
}
