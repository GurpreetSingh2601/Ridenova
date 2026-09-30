package com.ridenova.passenger.data

import com.ridenova.passenger.model.PaymentMethod
import com.ridenova.passenger.model.PlaceSuggestion
import org.json.JSONArray
import org.json.JSONObject

data class AccountPlaces(
    val home: PlaceSuggestion?,
    val work: PlaceSuggestion?,
    val recentDestinations: List<PlaceSuggestion>
)

/** Server-owned passenger preferences and development payment references. */
class AccountDataRepository(private val client: RideNovaHttpClient) {
    data class TestCheckout(val sessionId: String, val url: String)

    suspend fun startStripeTestSetup(): TestCheckout = when (val result = client.post("v1/passenger/payment-methods/setup", JSONObject())) {
        is ApiResult.Success -> TestCheckout(result.value.getString("sessionId"), result.value.getString("url"))
        is ApiResult.Failure -> error(result.message)
    }

    suspend fun syncStripeTestSetup(sessionId: String): List<PaymentMethod> {
        when (val result = client.post("v1/passenger/payment-methods/sync", JSONObject().put("sessionId", sessionId))) {
            is ApiResult.Success -> Unit
            is ApiResult.Failure -> error(result.message)
        }
        return loadPaymentMethods()
    }

    suspend fun authorizeTestRide(rideId: String): String = when (val result = client.post(
        "v1/passenger/rides/$rideId/authorize-test", JSONObject())) {
        is ApiResult.Success -> result.value.optString("status", "unknown")
        is ApiResult.Failure -> error(result.message)
    }
    suspend fun loadPlaces(): AccountPlaces = when (val result = client.get("v1/passenger/account-data")) {
        is ApiResult.Success -> places(result.value)
        is ApiResult.Failure -> error(result.message)
    }

    suspend fun savePlace(slot: String, place: PlaceSuggestion): AccountPlaces {
        when (val result = client.post("v1/passenger/saved-places", JSONObject()
            .put("action", "save").put("slot", slot).put("place", placeJson(place)))) {
            is ApiResult.Failure -> error(result.message)
            is ApiResult.Success -> Unit
        }
        return loadPlaces()
    }

    suspend fun removePlace(slot: String): AccountPlaces {
        when (val result = client.post("v1/passenger/saved-places", JSONObject().put("action", "remove").put("slot", slot))) {
            is ApiResult.Failure -> error(result.message)
            is ApiResult.Success -> Unit
        }
        return loadPlaces()
    }

    suspend fun addRecent(place: PlaceSuggestion): AccountPlaces = changeRecent("add", place)
    suspend fun removeRecent(place: PlaceSuggestion): AccountPlaces = changeRecent("remove", place)
    suspend fun clearRecent(): AccountPlaces = changeRecent("clear", null)

    private suspend fun changeRecent(action: String, place: PlaceSuggestion?): AccountPlaces {
        val body = JSONObject().put("action", action).apply { place?.let { put("place", placeJson(it)) } }
        return when (val result = client.post("v1/passenger/recent-destinations", body)) {
            is ApiResult.Success -> places(result.value)
            is ApiResult.Failure -> error(result.message)
        }
    }

    suspend fun loadPaymentMethods(): List<PaymentMethod> = when (val result = client.get("v1/passenger/payment-methods")) {
        is ApiResult.Success -> paymentMethods(result.value.optJSONArray("paymentMethods") ?: JSONArray())
        is ApiResult.Failure -> error(result.message)
    }

    suspend fun addDevelopmentCard(brand: String, last4: String, month: Int, year: Int): List<PaymentMethod> {
        val body = JSONObject().put("brand", brand).put("last4", last4)
            .put("expiryMonth", month).put("expiryYear", year)
        when (val result = client.post("v1/passenger/payment-methods", body)) {
            is ApiResult.Failure -> error(result.message)
            is ApiResult.Success -> Unit
        }
        return loadPaymentMethods()
    }

    suspend fun makeDefault(id: String): List<PaymentMethod> {
        when (val result = client.post("v1/passenger/payment-methods/$id/default", JSONObject())) {
            is ApiResult.Failure -> error(result.message)
            is ApiResult.Success -> Unit
        }
        return loadPaymentMethods()
    }

    suspend fun removePaymentMethod(id: String): List<PaymentMethod> {
        when (val result = client.post("v1/passenger/payment-methods/$id/remove", JSONObject())) {
            is ApiResult.Failure -> error(result.message)
            is ApiResult.Success -> Unit
        }
        return loadPaymentMethods()
    }

    private fun places(json: JSONObject): AccountPlaces {
        val saved = json.optJSONObject("savedPlaces") ?: JSONObject()
        val recent = json.optJSONArray("recentDestinations") ?: JSONArray()
        return AccountPlaces(
            home = saved.optJSONObject("home")?.let(::placeFromJson),
            work = saved.optJSONObject("work")?.let(::placeFromJson),
            recentDestinations = buildList {
                for (index in 0 until recent.length()) add(placeFromJson(recent.getJSONObject(index)))
            }
        )
    }

    private fun paymentMethods(array: JSONArray) = buildList {
        for (index in 0 until array.length()) {
            val json = array.getJSONObject(index)
            add(PaymentMethod(
                id = json.getString("id"), type = json.optString("type", "CARD"),
                brand = json.getString("brand"), last4 = json.getString("last4"),
                expiryMonth = json.getInt("expiryMonth"), expiryYear = json.getInt("expiryYear"),
                isDefault = json.optBoolean("isDefault"), developmentOnly = json.optBoolean("developmentOnly", true)
            ))
        }
    }

    private fun placeJson(place: PlaceSuggestion) = JSONObject()
        .put("name", place.name).put("address", place.address)
        .apply {
            place.latitude?.let { put("latitude", it) }
            place.longitude?.let { put("longitude", it) }
            place.placeId?.let { put("placeId", it) }
        }

    private fun placeFromJson(json: JSONObject) = PlaceSuggestion(
        name = json.optString("name"), address = json.optString("address"),
        latitude = if (json.has("latitude")) json.optDouble("latitude") else null,
        longitude = if (json.has("longitude")) json.optDouble("longitude") else null,
        placeId = json.optString("placeId").takeIf { it.isNotBlank() }
    )
}
