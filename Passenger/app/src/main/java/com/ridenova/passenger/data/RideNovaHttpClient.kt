package com.ridenova.passenger.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

sealed interface ApiResult<out T> {
    data class Success<T>(val value: T) : ApiResult<T>
    data class Failure(val statusCode: Int?, val message: String, val code: String? = null) : ApiResult<Nothing>
}

/** JSON transport with one serialized access-token refresh and retry. */
class RideNovaHttpClient(private val environment: AppEnvironment, private val sessionManager: SessionManager) {
    init {
        require(environment.environment == RideNovaEnvironment.DEVELOPMENT || environment.apiBaseUrl.startsWith("https://")) {
            "Staging and production require HTTPS"
        }
    }
    private val refreshMutex = Mutex()
    val configured: Boolean get() = environment.backendConfigured
    suspend fun post(path: String, body: JSONObject) = request("POST", path, body, true)
    suspend fun get(path: String) = request("GET", path, null, true)
    suspend fun patch(path: String, body: JSONObject) = request("PATCH", path, body, true)
    suspend fun publicPost(path: String, body: JSONObject) = request("POST", path, body, false)

    private suspend fun request(method: String, path: String, body: JSONObject?, authenticated: Boolean): ApiResult<JSONObject> = withContext(Dispatchers.IO) {
        if (!configured) return@withContext ApiResult.Failure(null, "RideNova backend is not configured")
        val usedToken = if (authenticated) sessionManager.accessToken() else null
        var result = execute(method, path, body, usedToken)
        // GET is read-only: one bounded retry after a connection failure is safe.
        // Never automatically replay POST/PATCH; the server may have committed a ride.
        if (method == "GET" && result is ApiResult.Failure && result.statusCode == null) {
            delay(400)
            result = execute(method, path, body, usedToken)
        }
        if (authenticated && result is ApiResult.Failure && result.statusCode == 401 && sessionManager.refreshToken() != null) {
            val refreshed = refreshMutex.withLock { if (sessionManager.accessToken() != usedToken) true else refreshTokens() }
            if (refreshed) result = execute(method, path, body, sessionManager.accessToken())
        }
        result
    }

    private fun refreshTokens(): Boolean {
        val refresh = sessionManager.refreshToken() ?: return false
        return when (val result = execute("POST", "v1/auth/refresh", JSONObject().put("refreshToken", refresh), null)) {
            is ApiResult.Success -> runCatching { saveTokens(result.value); true }.getOrDefault(false)
            is ApiResult.Failure -> {
                if (result.statusCode == 401) sessionManager.clearAuthentication()
                false
            }
        }
    }

    fun saveTokens(json: JSONObject) = sessionManager.saveTokens(
        json.getString("accessToken"), json.getString("refreshToken"),
        json.getLong("accessExpiresAtEpochMs"), json.getLong("refreshExpiresAtEpochMs"))

    private fun execute(method: String, path: String, body: JSONObject?, accessToken: String?): ApiResult<JSONObject> = runCatching {
        val endpoint = environment.apiBaseUrl.trimEnd('/') + "/" + path.trimStart('/')
        val connection = URL(endpoint).openConnection() as HttpURLConnection
        try {
            connection.apply {
                instanceFollowRedirects = false
                requestMethod = method; connectTimeout = 10_000; readTimeout = 15_000
                setRequestProperty("Accept", "application/json"); setRequestProperty("Content-Type", "application/json")
                setRequestProperty("X-RideNova-Session", sessionManager.sessionId())
                accessToken?.let { setRequestProperty("Authorization", "Bearer $it") }
                if (body != null) { doOutput = true; outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(body.toString()) } }
            }
            val status = connection.responseCode
            val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (status in 200..299) ApiResult.Success(if (text.isBlank()) JSONObject() else JSONObject(text))
            else {
                val error = runCatching { JSONObject(text) }.getOrNull()
                ApiResult.Failure(status, error?.optString("message")?.takeIf { it.isNotBlank() } ?: "RideNova API request failed ($status)",
                    error?.optString("code")?.takeIf { it.isNotBlank() })
            }
        } finally {
            // Disconnect even when writing the body, reading a response or parsing JSON throws.
            connection.disconnect()
        }
    }.getOrElse { ApiResult.Failure(null, it.localizedMessage ?: "Network request failed") }
}
