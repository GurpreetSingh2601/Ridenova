package com.ridenova.passenger.data

import com.ridenova.passenger.BuildConfig

enum class RideNovaEnvironment { DEVELOPMENT, STAGING, PRODUCTION }

data class AppEnvironment(
    val environment: RideNovaEnvironment,
    val apiBaseUrl: String
) {
    val backendConfigured: Boolean get() = apiBaseUrl.isNotBlank()

    companion object {
        fun current(): AppEnvironment {
            val environment = when (BuildConfig.RIDENOVA_ENVIRONMENT.lowercase()) {
                "production" -> RideNovaEnvironment.PRODUCTION
                "staging" -> RideNovaEnvironment.STAGING
                else -> RideNovaEnvironment.DEVELOPMENT
            }
            return AppEnvironment(environment, BuildConfig.RIDENOVA_API_BASE_URL.trim())
        }
    }
}
