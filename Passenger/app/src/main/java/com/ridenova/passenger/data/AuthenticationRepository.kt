package com.ridenova.passenger.data

import com.ridenova.passenger.model.RiderProfile
import org.json.JSONObject

data class OtpChallenge(val id: String, val developmentCode: String?, val expiresAtEpochMs: Long)
data class VerifiedAccount(val profile: RiderProfile, val profileComplete: Boolean, val migratedLegacySession: Boolean)

class AuthenticationRepository(private val client: RideNovaHttpClient, private val sessionManager: SessionManager) {
    val signedIn: Boolean get() = sessionManager.isSignedIn()
    suspend fun requestOtp(phone: String): OtpChallenge = when (val result = client.publicPost("v1/auth/request-otp", JSONObject().put("phone", phone))) {
        is ApiResult.Success -> OtpChallenge(result.value.getString("challengeId"), result.value.optString("developmentCode").takeIf { it.isNotBlank() }, result.value.getLong("expiresAtEpochMs"))
        is ApiResult.Failure -> error(result.message)
    }
    suspend fun verifyOtp(challengeId: String, code: String): VerifiedAccount = when (val result = client.publicPost("v1/auth/verify-otp", JSONObject().put("challengeId", challengeId).put("code", code))) {
        is ApiResult.Success -> { client.saveTokens(result.value); val passenger = result.value.getJSONObject("passenger"); VerifiedAccount(profile(passenger), passenger.optBoolean("profileComplete"), result.value.optBoolean("migratedLegacySession")) }
        is ApiResult.Failure -> error(result.message)
    }
    suspend fun loadProfile(): RiderProfile = when (val result = client.get("v1/passenger/me")) { is ApiResult.Success -> profile(result.value); is ApiResult.Failure -> error(result.message) }
    suspend fun updateProfile(value: RiderProfile): RiderProfile = when (val result = client.patch("v1/passenger/me", JSONObject().put("firstName", value.firstName).put("lastName", value.lastName).put("email", value.email))) {
        is ApiResult.Success -> profile(result.value); is ApiResult.Failure -> error(result.message)
    }
    suspend fun logout() {
        val refresh = sessionManager.refreshToken()
        runCatching { client.post("v1/auth/logout", JSONObject().apply { refresh?.let { put("refreshToken", it) } }) }
        sessionManager.clearAuthentication()
    }
    fun clearLocalSession() = sessionManager.clearAuthentication()
    private fun profile(json: JSONObject) = RiderProfile(json.optString("firstName"), json.optString("lastName"), json.optString("email"), json.optString("phone"))
}
