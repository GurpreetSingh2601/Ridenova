package com.ridenova.driver.data

import com.google.android.gms.maps.model.LatLng
import com.ridenova.driver.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.io.IOException

class DriverApiException(val status: Int, val code: String, message: String) : IllegalStateException(message)

/** Development-driver bearer transport; this token is embedded only in debug builds. */
class DriverHttpApi(private val baseUrl: String, private val devToken: String, private val fleet: Boolean = false) : DriverApiContract {
    init { require(baseUrl.startsWith("https://") || (BuildConfig.DEBUG && baseUrl.startsWith("http://"))) { "Driver API requires HTTPS outside debug builds" } }

    override suspend fun setAvailability(online: Boolean) { request("POST", "v1/driver/availability", JSONObject().put("online", online)) }

    override suspend fun currentOffer(): DriverOffer? = request("GET", "v1/driver/requests/current")
        .takeUnless { it.isEmptyObject() }?.let { json ->
            DriverOffer(json.getString("id"), coordinate(json.getJSONObject("pickup")),
                coordinate(json.getJSONObject("destination")), json.getLong("expiresAtEpochMs"))
        }

    override suspend fun accept(rideId: String) = changeStatus(rideId, "accept")
    override suspend fun decline(rideId: String) { request("POST", "v1/driver/rides/${safeId(rideId)}/decline", JSONObject()) }
    override suspend fun arrive(rideId: String) = changeStatus(rideId, "arrive")
    override suspend fun start(rideId: String) = changeStatus(rideId, "start")
    override suspend fun complete(rideId: String) = changeStatus(rideId, "complete")

    override suspend fun publishLocation(rideId: String, position: LatLng, recordedAtEpochMs: Long) {
        request("POST", "v1/driver/rides/${safeId(rideId)}/location", JSONObject()
            .put("latitude", position.latitude).put("longitude", position.longitude)
            .put("recordedAtEpochMs", recordedAtEpochMs))
    }

    override suspend fun activeRide(): DriverRideSnapshot? = request("GET", "v1/driver/rides/active")
        .takeUnless { it.isEmptyObject() }?.let(::snapshot)

    suspend fun json(method: String, path: String, body: JSONObject? = null) = request(method, path, body)

    private suspend fun changeStatus(id: String, action: String) = snapshot(
        request("POST", "v1/driver/rides/${safeId(id)}/$action", JSONObject()))

    private fun snapshot(json: JSONObject) = DriverRideSnapshot(
        json.getString("id"), json.getString("status"), json.getLong("updatedAtEpochMs"))

    private fun coordinate(json: JSONObject) = LatLng(json.getDouble("latitude"), json.getDouble("longitude"))
    private fun JSONObject.isEmptyObject() = length() == 0
    private fun safeId(id: String): String {
        require(id.matches(Regex("[a-zA-Z0-9_-]+"))) { "Invalid ride ID" }
        return id
    }

    private suspend fun request(method: String, path: String, body: JSONObject? = null): JSONObject =
        withContext(Dispatchers.IO) {
            require(devToken.isNotBlank() || path == "v2/fleet/register" || path in setOf("v2/fleet/auth/register", "v2/fleet/auth/login", "v2/fleet/auth/recover")) { "Driver access is missing" }
            val route = if (fleet && path.startsWith("v1/driver/")) path.replaceFirst("v1/driver/", "v2/fleet/driver/") else path
            // GET is safe to replay after a transport failure. Never replay POST: an
            // ambiguous timeout can mean the server already accepted a ride or mutation.
            var readAttempt = 0
            while (true) {
            val connection = (URL(baseUrl.trimEnd('/') + "/" + route).openConnection() as HttpURLConnection)
            try {
                connection.instanceFollowRedirects = false
                connection.requestMethod = method
                connection.connectTimeout = 10_000
                connection.readTimeout = 15_000
                connection.setRequestProperty("Accept", "application/json")
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("Authorization", "Bearer $devToken")
                if (body != null) {
                    connection.doOutput = true
                    connection.outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(body.toString()) }
                }
                val code = connection.responseCode
                val content = (if (code in 200..299) connection.inputStream else connection.errorStream)
                    ?.bufferedReader()?.use { it.readText() }.orEmpty()
                if (code !in 200..299) {
                    val message = runCatching { JSONObject(content).optString("message") }.getOrNull()
                    if (code == 404 && (path.startsWith("v2/fleet/auth/") || path.endsWith("login-details") || path.endsWith("logout"))) {
                        throw DriverApiException(code, "SERVER_UPGRADE_REQUIRED", "This server does not support current Driver access. Stop the older server and start the shared backend included with Build 41 using your existing database.")
                    }
                    throw DriverApiException(code, runCatching { JSONObject(content).optString("code") }.getOrDefault(""),
                        message?.takeIf { it.isNotBlank() } ?: "Driver API failed (HTTP $code)")
                }
                return@withContext if (content.isBlank()) JSONObject() else JSONObject(content)
            } catch (ex: IOException) {
                if (method != "GET" || readAttempt >= 1) throw ex
                readAttempt++
                kotlinx.coroutines.delay(350L)
            } finally {
                connection.disconnect()
            }
            }
            @Suppress("UNREACHABLE_CODE") JSONObject()
        }
}
