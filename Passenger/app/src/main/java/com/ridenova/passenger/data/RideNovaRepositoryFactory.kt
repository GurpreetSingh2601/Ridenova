package com.ridenova.passenger.data

import android.content.Context

/**
 * Single composition point for passenger data. Development currently uses the local prototype
 * repository, while the HTTP client/session boundary is initialized now so screens do not need
 * to be rewritten when dev/staging API URLs are switched on.
 */
data class RideNovaServices(
    val repository: RideNovaRepository,
    val httpClient: RideNovaHttpClient,
    val sessionManager: SessionManager,
    val environment: AppEnvironment,
    val authentication: AuthenticationRepository,
    val accountData: AccountDataRepository
)

object RideNovaRepositoryFactory {
    fun create(context: Context, localStore: RideNovaLocalStore): RideNovaServices {
        val appContext = context.applicationContext
        val environment = AppEnvironment.current()
        val session = SessionManager(appContext)
        val http = RideNovaHttpClient(environment, session)
        // Never silently select the obsolete manual-button prototype for a packaged build.
        // The build configuration also checks this, but retain a runtime guard for stale APKs.
        check(environment.backendConfigured) {
            "RideNova backend URL is missing. Set RIDENOVA_API_BASE_URL in Passenger gradle.properties and rebuild."
        }
        val repository: RideNovaRepository = BackendRideNovaRepository(http)
        return RideNovaServices(
            repository = repository,
            httpClient = http,
            sessionManager = session,
            environment = environment,
            authentication = AuthenticationRepository(http, session),
            accountData = AccountDataRepository(http)
        )
    }
}
