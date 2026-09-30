@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.ridenova.passenger.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import android.content.Intent
import android.net.Uri
import com.ridenova.passenger.R
import com.ridenova.passenger.BuildConfig
import com.google.android.libraries.places.api.Places
import com.google.android.libraries.places.api.model.AutocompletePrediction
import com.google.android.libraries.places.api.model.Place
import com.google.android.libraries.places.api.net.FetchPlaceRequest
import com.google.android.libraries.places.api.net.FindAutocompletePredictionsRequest
import com.ridenova.passenger.data.DemoData
import com.ridenova.passenger.data.FareEstimator
import com.ridenova.passenger.data.GoogleRoutesService
import com.ridenova.passenger.data.TripPrototypeFactory
import com.ridenova.passenger.data.RideNovaLocalStore
import com.ridenova.passenger.data.RideNovaRepositoryFactory
import com.ridenova.passenger.data.QuoteRequest
import com.ridenova.passenger.data.QuoteResponse
import com.ridenova.passenger.data.RideNovaRepository
import com.ridenova.passenger.data.CreateRideRequest
import com.ridenova.passenger.data.OtpChallenge
import com.ridenova.passenger.model.*
import com.ridenova.passenger.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.util.Date

private object Routes {
    const val SPLASH = "splash"
    const val WELCOME = "welcome"
    const val PHONE = "phone"
    const val OTP = "otp"
    const val PROFILE = "profile"
    const val ACCOUNT_PROFILE = "account_profile"
    const val HOME = "home"
    const val SEARCH = "search"
    const val RIDES = "rides"
    const val SCHEDULE = "schedule"
    const val CONFIRM = "confirm"
    const val MATCHING = "matching"
    const val TRIPS = "trips"
    const val ACCOUNT = "account"
    const val PAYMENT = "payment"
    const val SAVED_PLACES = "saved_places"
    const val SAFETY = "safety"
    const val LANGUAGE = "language"
    const val HELP = "help"
    const val APPEARANCE = "appearance"
    const val TRIP_DETAIL = "trip_detail"
}

@Composable
fun RideNovaApp(
    themeMode: RideNovaThemeMode,
    onThemeModeChange: (RideNovaThemeMode) -> Unit
) {
    val nav = rememberNavController()
    val context = LocalContext.current
    val localStore = remember { RideNovaLocalStore(context.applicationContext) }
    val initialProfile = remember { localStore.loadProfile() }
    val initialTrips = remember { if (BuildConfig.RIDENOVA_API_BASE_URL.isBlank()) localStore.loadTrips() else emptyList() }
    val initialRecentDestinations = remember { localStore.loadRecentDestinations() }
    val initialSavedHome = remember { localStore.loadSavedPlace("home") }
    val initialSavedWork = remember { localStore.loadSavedPlace("work") }
    val services = remember { RideNovaRepositoryFactory.create(context.applicationContext, localStore) }
    val repository = services.repository
    val authentication = services.authentication
    val accountData = services.accountData
    val appScope = rememberCoroutineScope()
    val initialDestination = remember {
        when {
            services.environment.backendConfigured && authentication.signedIn && !initialProfile?.displayName.isNullOrBlank() -> Routes.HOME
            services.environment.backendConfigured && authentication.signedIn -> Routes.PROFILE
            services.environment.backendConfigured -> Routes.SPLASH
            localStore.isOnboardingComplete() -> Routes.HOME
            else -> Routes.SPLASH
        }
    }

    var riderProfile by remember { mutableStateOf(initialProfile) }
    var draft by remember { mutableStateOf(BookingDraft()) }
    var trips by remember { mutableStateOf(initialTrips) }
    var recentDestinations by remember { mutableStateOf(initialRecentDestinations) }
    var savedHome by remember { mutableStateOf(initialSavedHome) }
    var savedWork by remember { mutableStateOf(initialSavedWork) }
    var savePlaceTarget by remember { mutableStateOf<String?>(null) }
    var bookingBusy by remember { mutableStateOf(false) }
    var bookingError by remember { mutableStateOf<String?>(null) }
    var reviewedQuote by remember(draft) { mutableStateOf<QuoteResponse?>(null) }
    var syncError by remember { mutableStateOf<String?>(null) }
    var pendingPhone by remember { mutableStateOf("") }
    var otpChallenge by remember { mutableStateOf<OtpChallenge?>(null) }
    var authBusy by remember { mutableStateOf(false) }
    var authError by remember { mutableStateOf<String?>(null) }
    var signedIn by remember { mutableStateOf(authentication.signedIn) }
    var accountDataError by remember { mutableStateOf<String?>(null) }
    var accountDataBusy by remember { mutableStateOf(false) }
    var paymentMethods by remember {
        mutableStateOf(
            if (services.environment.backendConfigured) emptyList()
            else listOf(PaymentMethod("pm_offline_4242", brand = "Visa", last4 = "4242", expiryMonth = 12, expiryYear = 2030, isDefault = true))
        )
    }
    var activeTripId by remember {
        mutableStateOf(
            initialTrips.firstOrNull {
                it.status in setOf(TripStatus.SEARCHING, TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_ARRIVED, TripStatus.TRIP_STARTED)
            }?.id
        )
    }
    var completionPrompt by rememberSaveable { mutableStateOf<String?>(null) }

    fun rememberDestination(place: PlaceSuggestion) {
        recentDestinations = localStore.addRecentDestination(place)
        if (services.environment.backendConfigured && signedIn) appScope.launch {
            runCatching { accountData.addRecent(place) }
                .onSuccess { data ->
                    recentDestinations = data.recentDestinations
                    localStore.replaceRecentDestinations(data.recentDestinations)
                    accountDataError = null
                }
                .onFailure { accountDataError = it.localizedMessage ?: "Could not sync recent destinations" }
        }
    }

    fun updateTrip(updated: RideTrip) {
        val previous = trips.firstOrNull { it.id == updated.id }
        if (updated.status == TripStatus.COMPLETED && previous?.status != TripStatus.COMPLETED) {
            completionPrompt = updated.id
        }
        // A restored ride may not yet exist in the locally cached list.
        trips = if (trips.any { it.id == updated.id }) {
            trips.map { if (it.id == updated.id) updated else it }
        } else listOf(updated) + trips
    }

    LaunchedEffect(trips) {
        if (!services.environment.backendConfigured) localStore.saveTrips(trips)
    }

    LaunchedEffect(signedIn) {
        if (services.environment.backendConfigured && signedIn) {
            runCatching { authentication.loadProfile() }
                .onSuccess {
                    riderProfile = it; localStore.saveProfile(it)
                    if (it.displayName.isBlank() && nav.currentDestination?.route != Routes.PROFILE) {
                        nav.navigate(Routes.PROFILE) { popUpTo(nav.graph.startDestinationId) { inclusive = true } }
                    } else if (it.displayName.isNotBlank() && nav.currentDestination?.route == Routes.PROFILE) {
                        nav.navigate(Routes.HOME) { popUpTo(nav.graph.startDestinationId) { inclusive = true } }
                    }
                }
                .onFailure {
                    if (!authentication.signedIn) {
                        riderProfile = null
                        nav.navigate(Routes.WELCOME) { popUpTo(nav.graph.startDestinationId) { inclusive = true } }
                    }
                }
        }
    }

    LaunchedEffect(repository, signedIn) {
        if (services.environment.backendConfigured && signedIn) {
            while (true) {
                runCatching { repository.listRides() }.onSuccess { remote ->
                    syncError = null
                    if (completionPrompt == null && trips.isNotEmpty()) {
                        completionPrompt = remote.firstOrNull { fetched ->
                            fetched.status == TripStatus.COMPLETED &&
                                trips.firstOrNull { it.id == fetched.id }?.status != TripStatus.COMPLETED
                        }?.id
                    }
                    // Preserve a just-created booking while a concurrent list request is still
                    // returning an older snapshot. The booking API is authoritative for creation;
                    // the list endpoint may lag behind that response for one refresh cycle.
                    val merged = remote.map { fetched ->
                        trips.firstOrNull { it.id == fetched.id && it.updatedAtEpochMs > fetched.updatedAtEpochMs } ?: fetched
                    }
                    val pending = trips.filter { local ->
                        local.id == activeTripId &&
                            local.status in liveTripStatuses &&
                            merged.none { it.id == local.id } &&
                            System.currentTimeMillis() - local.requestedAtEpochMs < 30_000L
                    }
                    trips = pending + merged
                    if (activeTripId == null || trips.none { it.id == activeTripId }) {
                        activeTripId = trips.firstOrNull {
                            it.status in setOf(TripStatus.SEARCHING, TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_ARRIVED, TripStatus.TRIP_STARTED)
                        }?.id
                    }
                }.onFailure {
                    if (!authentication.signedIn) {
                        signedIn = false
                        syncError = "Your session expired. Sign in again to access your rides."
                        nav.navigate(Routes.WELCOME) { popUpTo(nav.graph.startDestinationId) { inclusive = true } }
                    } else syncError = "Connection lost. Trip status may be out of date; reconnect before taking action."
                }
                delay(5_000)
            }
        }
    }

    LaunchedEffect(accountData, signedIn) {
        if (services.environment.backendConfigured && signedIn) {
            accountDataBusy = true
            runCatching { accountData.loadPlaces() }
                .onSuccess { data ->
                    savedHome = data.home; savedWork = data.work; recentDestinations = data.recentDestinations
                    data.home?.let { localStore.saveSavedPlace("home", it) } ?: localStore.clearSavedPlace("home")
                    data.work?.let { localStore.saveSavedPlace("work", it) } ?: localStore.clearSavedPlace("work")
                    localStore.replaceRecentDestinations(data.recentDestinations)
                    accountDataError = null
                }
                .onFailure { accountDataError = it.localizedMessage ?: "Could not load account places" }
            runCatching { accountData.loadPaymentMethods() }
                .onSuccess { paymentMethods = it; accountDataError = null }
                .onFailure { accountDataError = it.localizedMessage ?: "Could not load payment methods" }
            accountDataBusy = false
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        NavHost(
            navController = nav,
            startDestination = initialDestination,
            enterTransition = {
                val from = initialState.destination.route
                val to = targetState.destination.route
                val direction = topLevelDirection(from, to)
                fadeIn(tween(180, easing = FastOutSlowInEasing)) +
                    slideInHorizontally(tween(210, easing = FastOutSlowInEasing)) { fullWidth ->
                        when {
                            direction > 0 -> fullWidth / 12
                            direction < 0 -> -fullWidth / 12
                            else -> fullWidth / 14
                        }
                    }
            },
            exitTransition = {
                val from = initialState.destination.route
                val to = targetState.destination.route
                val direction = topLevelDirection(from, to)
                fadeOut(tween(140, easing = FastOutSlowInEasing)) +
                    slideOutHorizontally(tween(180, easing = FastOutSlowInEasing)) { fullWidth ->
                        when {
                            direction > 0 -> -fullWidth / 18
                            direction < 0 -> fullWidth / 18
                            else -> -fullWidth / 20
                        }
                    }
            },
            popEnterTransition = {
                fadeIn(tween(180, easing = FastOutSlowInEasing)) +
                    slideInHorizontally(tween(210, easing = FastOutSlowInEasing)) { fullWidth -> -fullWidth / 10 }
            },
            popExitTransition = {
                fadeOut(tween(140, easing = FastOutSlowInEasing)) +
                    slideOutHorizontally(tween(180, easing = FastOutSlowInEasing)) { fullWidth -> fullWidth / 16 }
            }
        ) {
        composable(Routes.SPLASH) { SplashScreen { nav.navigate(Routes.WELCOME) { popUpTo(Routes.SPLASH) { inclusive = true } } } }
        composable(Routes.WELCOME) { WelcomeScreen { nav.navigate(Routes.PHONE) } }
        composable(Routes.PHONE) {
            PhoneScreen(pendingPhone, authBusy, authError, services.environment.backendConfigured,
                onBack = { nav.popBackStack() }, onContinue = { phone ->
                    pendingPhone = phone; authBusy = true; authError = null
                    appScope.launch {
                        if (services.environment.backendConfigured) {
                            runCatching { authentication.requestOtp(phone) }
                                .onSuccess { otpChallenge = it; authBusy = false; nav.navigate(Routes.OTP) }
                                .onFailure { authBusy = false; authError = it.localizedMessage }
                        } else {
                            otpChallenge = OtpChallenge("offline", "123456", System.currentTimeMillis() + 300_000)
                            authBusy = false; nav.navigate(Routes.OTP)
                        }
                    }
                })
        }
        composable(Routes.OTP) {
            OtpScreen(pendingPhone, otpChallenge?.developmentCode, authBusy, authError,
                onBack = { authError = null; nav.popBackStack() }, onVerified = { code ->
                    val challenge = otpChallenge ?: return@OtpScreen
                    authBusy = true; authError = null
                    appScope.launch {
                        if (services.environment.backendConfigured) {
                            runCatching { authentication.verifyOtp(challenge.id, code) }
                                .onSuccess { verified ->
                                    signedIn = true; riderProfile = verified.profile; localStore.saveProfile(verified.profile); authBusy = false
                                    nav.navigate(if (verified.profileComplete) Routes.HOME else Routes.PROFILE) { popUpTo(Routes.WELCOME) { inclusive = true } }
                                }.onFailure { authBusy = false; authError = it.localizedMessage }
                        } else if (code == "123456") {
                            authBusy = false; nav.navigate(Routes.PROFILE)
                        } else { authBusy = false; authError = "Incorrect development code" }
                    }
                })
        }
        composable(Routes.PROFILE) {
            ProfileScreen(riderProfile, riderProfile?.phone ?: pendingPhone, authBusy, authError) { profile ->
                authBusy = true; authError = null
                appScope.launch {
                    val saved = if (services.environment.backendConfigured) runCatching { authentication.updateProfile(profile) } else Result.success(profile)
                    saved.onSuccess { riderProfile = it; localStore.saveProfile(it); authBusy = false; nav.navigate(Routes.HOME) { popUpTo(Routes.WELCOME) { inclusive = true } } }
                        .onFailure { authBusy = false; authError = it.localizedMessage }
                }
            }
        }
        composable(Routes.HOME) {
            HomeScreen(
                nav = nav,
                recentDestinations = recentDestinations,
                savedHome = savedHome,
                savedWork = savedWork,
                activeTrip = trips.firstOrNull { it.id == activeTripId && it.status in liveTripStatuses }
                    ?: trips.filter { it.status in liveTripStatuses }.maxByOrNull { it.updatedAtEpochMs }
                    ?: trips.filter { it.status in pastTripStatuses }.maxByOrNull { it.updatedAtEpochMs },
                onResumeTrip = { selected ->
                    activeTripId = selected.id
                    nav.navigate(if (selected.status in liveTripStatuses) Routes.MATCHING else Routes.TRIP_DETAIL)
                },
                onSearchDestination = {
                    savePlaceTarget = null
                    nav.navigate(Routes.SEARCH)
                },
                onSavedPlace = { place ->
                    if (place == null) {
                        nav.navigate(Routes.SAVED_PLACES)
                    } else {
                        rememberDestination(place)
                        draft = draft.copy(destination = place, routeEstimate = null, scheduled = false, scheduleLabel = "Now", scheduledAtEpochMs = null, scheduleTimeZone = null)
                        nav.navigate(Routes.RIDES)
                    }
                },
                onRecentDestination = { place ->
                    // A cancelled Home/Work edit must never leak into a normal destination tap.
                    savePlaceTarget = null
                    rememberDestination(place)
                    draft = draft.copy(destination = place, routeEstimate = null, scheduled = false, scheduleLabel = "Now", scheduledAtEpochMs = null, scheduleTimeZone = null)
                    nav.navigate(Routes.RIDES)
                },
                onPickupResolved = { lat, lng, address ->
                    draft = draft.copy(
                        pickup = PlaceSuggestion(
                            name = "Current location",
                            address = address ?: "Current GPS location",
                            latitude = lat,
                            longitude = lng
                        ),
                        routeEstimate = null
                    )
                }
            )
        }
        composable(Routes.SEARCH) {
            SearchScreen(
                recentDestinations = recentDestinations,
                screenTitle = when (savePlaceTarget) {
                    "home" -> "Set Home"
                    "work" -> "Set Work"
                    else -> "Choose destination"
                },
                searchHint = when (savePlaceTarget) {
                    "home" -> "Search for your home address"
                    "work" -> "Search for your work address"
                    else -> "Where to?"
                },
                onBack = {
                    savePlaceTarget = null
                    nav.popBackStack()
                },
                onClearRecent = {
                    localStore.clearRecentDestinations()
                    recentDestinations = emptyList()
                    if (services.environment.backendConfigured && signedIn) appScope.launch {
                        runCatching { accountData.clearRecent() }
                            .onSuccess { accountDataError = null }
                            .onFailure { accountDataError = it.localizedMessage ?: "Could not clear recent destinations" }
                    }
                },
                onRemoveRecent = { place ->
                    recentDestinations = localStore.removeRecentDestination(place)
                    if (services.environment.backendConfigured && signedIn) appScope.launch {
                        runCatching { accountData.removeRecent(place) }
                            .onSuccess { accountDataError = null }
                            .onFailure { accountDataError = it.localizedMessage ?: "Could not remove recent destination" }
                    }
                },
                onPlace = { place ->
                    val target = savePlaceTarget
                    if (target != null) {
                        localStore.saveSavedPlace(target, place)
                        if (target == "home") savedHome = place else savedWork = place
                        if (services.environment.backendConfigured && signedIn) appScope.launch {
                            runCatching { accountData.savePlace(target, place) }
                                .onSuccess { accountDataError = null }
                                .onFailure { accountDataError = it.localizedMessage ?: "Could not sync saved place" }
                        }
                        savePlaceTarget = null
                        nav.popBackStack()
                    } else {
                        rememberDestination(place)
                        draft = draft.copy(destination = place, routeEstimate = null, scheduled = false, scheduleLabel = "Now", scheduledAtEpochMs = null, scheduleTimeZone = null)
                        nav.navigate(Routes.RIDES)
                    }
                }
            )
        }
        composable(Routes.RIDES) {
            RideSelectionScreen(
                draft = draft,
                onBack = { nav.popBackStack() },
                onSelect = { draft = draft.copy(selectedTier = it) },
                onRouteSelected = { draft = draft.copy(routeEstimate = it) },
                onSchedule = { nav.navigate(Routes.SCHEDULE) },
                onContinue = { nav.navigate(Routes.CONFIRM) }
            )
        }
        composable(Routes.SCHEDULE) {
            ScheduleScreen(
                onBack = { nav.popBackStack() },
                initialPickup = draft.scheduledAtEpochMs,
                onChoose = { at, zone ->
                    draft = draft.copy(scheduled = at != null, scheduledAtEpochMs = at, scheduleTimeZone = zone,
                        scheduleLabel = if (at != null && zone != null) ScheduleTime.label(at, zone) else "Now")
                    nav.popBackStack()
                }
            )
        }
        composable(Routes.CONFIRM) {
            var nearbyDriver by remember(draft.pickup, draft.selectedTier) { mutableStateOf<DriverAvailability?>(null) }
            var nearbyDriverChecking by remember(draft.pickup, draft.selectedTier) { mutableStateOf(true) }
            LaunchedEffect(draft, signedIn, services.environment.backendConfigured) {
                if (!services.environment.backendConfigured || !signedIn || reviewedQuote != null) return@LaunchedEffect
                val destination = draft.destination ?: return@LaunchedEffect
                val route = draft.routeEstimate ?: FareEstimator.route(draft.pickup, destination)
                if (route == null) return@LaunchedEffect
                bookingBusy = true
                bookingError = null
                runCatching {
                    repository.quote(
                        QuoteRequest(
                            pickup = draft.pickup,
                            destination = destination,
                            route = route,
                            scheduled = draft.scheduled,
                            scheduleLabel = draft.scheduleLabel,
                            scheduledAtEpochMs = draft.scheduledAtEpochMs,
                            scheduleTimeZone = draft.scheduleTimeZone
                        )
                    )
                }.onSuccess { reviewedQuote = it }
                    .onFailure { bookingError = it.localizedMessage ?: "Current fare is unavailable" }
                bookingBusy = false
            }
            LaunchedEffect(draft.pickup, draft.selectedTier, services.environment.backendConfigured) {
                if (!services.environment.backendConfigured || draft.scheduled) {
                    nearbyDriverChecking = false
                    nearbyDriver = null
                    return@LaunchedEffect
                }
                while (true) {
                    nearbyDriverChecking = true
                    nearbyDriver = runCatching { repository.nearbyDriverAvailability(draft.pickup, draft.selectedTier) }.getOrNull()
                    nearbyDriverChecking = false
                    delay(5_000)
                }
            }
            ConfirmationScreen(
                draft = draft,
                reviewedOption = reviewedQuote?.options?.firstOrNull { it.tier == draft.selectedTier },
                serverRoute = reviewedQuote?.serverRoute,
                routeChangeReason = reviewedQuote?.routeChangeReason,
                busy = bookingBusy,
                errorMessage = bookingError,
                paymentMethod = paymentMethods.firstOrNull { it.isDefault } ?: paymentMethods.firstOrNull(),
                nearbyDriver = nearbyDriver,
                nearbyDriverChecking = nearbyDriverChecking,
                onOpenPayment = { nav.navigate(Routes.PAYMENT) },
                onBack = { if (!bookingBusy) nav.popBackStack() },
                onRequest = {
                    if (!bookingBusy) appScope.launch {
                        bookingBusy = true
                        bookingError = null
                        runCatching {
                            val route = draft.routeEstimate ?: FareEstimator.route(draft.pickup, draft.destination)
                                ?: error("Route estimate is unavailable")
                            val quote = reviewedQuote?.takeIf { it.expiresAtEpochMs > System.currentTimeMillis() } ?: repository.quote(
                                QuoteRequest(
                                    pickup = draft.pickup,
                                    destination = draft.destination ?: error("Destination is missing"),
                                    route = route,
                                    scheduled = draft.scheduled,
                                    scheduleLabel = draft.scheduleLabel,
                                    scheduledAtEpochMs = draft.scheduledAtEpochMs,
                                    scheduleTimeZone = draft.scheduleTimeZone
                                )
                            )
                            if (reviewedQuote !== quote) {
                                reviewedQuote = quote
                                bookingBusy = false
                                return@launch
                            }
                            val option = quote.options.first { it.tier == draft.selectedTier }
                            val paymentMethod = paymentMethods.firstOrNull { it.isDefault } ?: paymentMethods.firstOrNull()
                                ?: error("Choose a payment method before confirming")
                            repository.createRide(CreateRideRequest(draft.copy(routeEstimate = route), option, quote.quoteToken, paymentMethod.id))
                        }.onSuccess { trip ->
                            trips = listOf(trip) + trips.filterNot { it.id == trip.id }
                            activeTripId = trip.id
                            bookingBusy = false
                            if (trip.status == TripStatus.SCHEDULED) {
                                nav.navigate(Routes.TRIPS) { popUpTo(Routes.HOME); launchSingleTop = true }
                            } else {
                                nav.navigate(Routes.MATCHING)
                            }
                        }.onFailure { error ->
                            bookingBusy = false
                            bookingError = error.localizedMessage ?: "Ride request could not be created"
                        }
                    }
                }
            )
        }
        composable(Routes.MATCHING) {
            // A matching destination may compose before its just-created ride is visible
            // in a concurrent list response. Never show the empty-state immediately.
            var recoveryInProgress by remember(activeTripId) { mutableStateOf(true) }
            var recoveryError by remember(activeTripId) { mutableStateOf<String?>(null) }
            val trip = trips.firstOrNull { it.id == activeTripId }
                ?: trips.firstOrNull { it.status in liveTripStatuses }
            LaunchedEffect(activeTripId, trip?.id, signedIn) {
                if (trip != null || !services.environment.backendConfigured || !signedIn) {
                    recoveryInProgress = false
                    return@LaunchedEffect
                }
                recoveryInProgress = true
                repeat(3) { attempt ->
                    val recovered = runCatching {
                        val selectedId = activeTripId
                        if (selectedId != null) {
                            runCatching { repository.getRide(selectedId) }.getOrNull()
                        } else null
                    }.getOrNull()
                    if (recovered != null) {
                        updateTrip(recovered)
                        activeTripId = recovered.id
                        recoveryError = null
                        recoveryInProgress = false
                        return@LaunchedEffect
                    }
                    runCatching { repository.listRides() }
                        .onSuccess { remote ->
                            val live = remote.firstOrNull { it.id == activeTripId }
                                ?: remote.firstOrNull { it.status in liveTripStatuses }
                            if (live != null) {
                                trips = listOf(live) + trips.filterNot { it.id == live.id }
                                activeTripId = live.id
                                recoveryError = null
                                recoveryInProgress = false
                                return@LaunchedEffect
                            }
                            if (attempt == 2) recoveryError = "No current ride was found on the server. Check Trips before booking again."
                        }.onFailure { error ->
                            recoveryError = "Could not load your ride. Check your connection and open Trips before booking again."
                        }
                    if (attempt < 2) delay(700)
                }
                recoveryInProgress = false
            }
            if (trip == null && recoveryInProgress) {
                Scaffold(topBar = { TopAppBar(title = { Text("Finding your ride") }) }) { pad ->
                    Column(Modifier.fillMaxSize().padding(pad).padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center) {
                        CircularProgressIndicator()
                        Spacer(Modifier.height(20.dp))
                        Text("Connecting to your ride…", fontWeight = FontWeight.SemiBold)
                        Text("Please wait while we restore your booking. Do not book again.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            } else MatchingScreen(
                trip = trip,
                backendMode = services.environment.backendConfigured,
                repository = repository,
                syncError = recoveryError ?: syncError,
                onTripUpdate = { updateTrip(it) },
                onOpenTrips = { nav.navigate(Routes.TRIPS) { launchSingleTop = true } },
                onReturnHome = {
                    activeTripId = null
                    draft = BookingDraft(pickup = draft.pickup)
                    nav.navigate(Routes.HOME) {
                        popUpTo(Routes.HOME) { inclusive = true }
                    }
                }
            )
        }
        composable(Routes.TRIPS) {
            // Match the Home tab's navigation on system Back (including gesture Back).
            BackHandler { navigateTopLevel(nav, Routes.HOME) }
            TripsScreen(
                nav = nav,
                trips = trips,
                backendMode = services.environment.backendConfigured,
                repository = repository,
                syncError = syncError,
                onTripUpdate = { updateTrip(it) },
                onOpenTrip = { tripId ->
                    activeTripId = tripId
                    val selectedTrip = trips.firstOrNull { it.id == tripId }
                    if (selectedTrip?.status in setOf(TripStatus.SEARCHING, TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_ARRIVED, TripStatus.TRIP_STARTED)) {
                        nav.navigate(Routes.MATCHING)
                    } else {
                        nav.navigate(Routes.TRIP_DETAIL)
                    }
                },
                onStartScheduled = { tripId ->
                    if (services.environment.backendConfigured) return@TripsScreen
                    trips.firstOrNull { it.id == tripId }?.let { trip ->
                        val now = System.currentTimeMillis()
                        val updated = trip.copy(
                            status = TripStatus.SEARCHING,
                            updatedAtEpochMs = now,
                            graceEndsAtEpochMs = now + 120_000L
                        )
                        updateTrip(updated)
                        activeTripId = tripId
                        nav.navigate(Routes.MATCHING)
                    }
                }
            )
        }
        composable(Routes.TRIP_DETAIL) {
            val trip = trips.firstOrNull { it.id == activeTripId }
            TripDetailScreen(
                trip = trip,
                repository = repository,
                onAuthorizeTest = { rideId -> accountData.authorizeTestRide(rideId) },
                onBack = { nav.popBackStack() },
                onOpenLiveRide = { nav.navigate(Routes.MATCHING) },
                onRideAgain = { previousTrip ->
                    previousTrip.draft.destination?.let(::rememberDestination)
                    draft = previousTrip.draft.copy(
                        pickup = draft.pickup,
                        routeEstimate = null,
                        scheduled = false,
                        scheduleLabel = "Now",
                        scheduledAtEpochMs = null,
                        scheduleTimeZone = null
                    )
                    nav.navigate(Routes.RIDES)
                }
            )
        }
        composable(Routes.ACCOUNT) {
            BackHandler { navigateTopLevel(nav, Routes.HOME) }
            AccountScreen(nav, themeMode, riderProfile, services.environment.backendConfigured,
                onEditProfile = { authError = null; nav.navigate(Routes.ACCOUNT_PROFILE) },
                onLogout = {
                    appScope.launch {
                        if (services.environment.backendConfigured) authentication.logout()
                        signedIn = false; riderProfile = null; trips = emptyList(); activeTripId = null
                        recentDestinations = emptyList(); savedHome = null; savedWork = null
                        paymentMethods = emptyList(); accountDataError = null
                        localStore.clearPassengerData()
                        nav.navigate(Routes.WELCOME) { popUpTo(nav.graph.id) { inclusive = true } }
                    }
                })
        }
        composable(Routes.ACCOUNT_PROFILE) {
            ProfileScreen(riderProfile, riderProfile?.phone.orEmpty(), authBusy, authError,
                title = "Edit profile", buttonLabel = "Save changes", onBack = { if (!authBusy) nav.popBackStack() }) { profile ->
                authBusy = true; authError = null
                appScope.launch {
                    val saved = if (services.environment.backendConfigured) runCatching { authentication.updateProfile(profile) } else Result.success(profile)
                    saved.onSuccess { riderProfile = it; localStore.saveProfile(it); authBusy = false; nav.popBackStack() }
                        .onFailure { authBusy = false; authError = it.localizedMessage }
                }
            }
        }
        composable(Routes.PAYMENT) {
            val context = LocalContext.current
            val checkoutPrefs = remember { context.getSharedPreferences("ridenova_test_checkout", android.content.Context.MODE_PRIVATE) }
            var pendingCheckout by remember { mutableStateOf(checkoutPrefs.getString("sessionId", null)) }
            PaymentMethodsScreen(
                methods = paymentMethods,
                busy = accountDataBusy,
                errorMessage = accountDataError,
                backendMode = services.environment.backendConfigured,
                staging = BuildConfig.RIDENOVA_ENVIRONMENT == "staging",
                pendingTestSetup = pendingCheckout != null,
                onStartTestSetup = {
                    accountDataBusy = true; accountDataError = null
                    appScope.launch {
                        runCatching { accountData.startStripeTestSetup() }
                            .onSuccess { session ->
                                pendingCheckout = session.sessionId
                                checkoutPrefs.edit().putString("sessionId", session.sessionId).apply()
                                accountDataBusy = false
                                runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(session.url))) }
                                    .onFailure { accountDataError = "Open test checkout failed: " + it.localizedMessage }
                            }.onFailure { accountDataError = it.localizedMessage; accountDataBusy = false }
                    }
                },
                onVerifyTestSetup = {
                    val sid = pendingCheckout
                    if (sid != null) {
                        accountDataBusy = true; accountDataError = null
                        appScope.launch {
                            runCatching { accountData.syncStripeTestSetup(sid) }
                                .onSuccess { paymentMethods = it; pendingCheckout = null; checkoutPrefs.edit().remove("sessionId").apply() }
                                .onFailure { accountDataError = it.localizedMessage }
                            accountDataBusy = false
                        }
                    }
                },
                onBack = { nav.popBackStack() },
                onReturnToBooking = {
                    if (nav.previousBackStackEntry?.destination?.route == Routes.CONFIRM) nav.popBackStack()
                    else nav.navigate(Routes.CONFIRM) { launchSingleTop = true }
                },
                fromBooking = nav.previousBackStackEntry?.destination?.route == Routes.CONFIRM,
                onAddDevelopmentCard = { brand, last4, month, year ->
                    if (services.environment.backendConfigured) {
                        accountDataBusy = true; accountDataError = null
                        appScope.launch {
                            runCatching { accountData.addDevelopmentCard(brand, last4, month, year) }
                                .onSuccess { paymentMethods = it; accountDataBusy = false }
                                .onFailure { accountDataError = it.localizedMessage; accountDataBusy = false }
                        }
                    }
                },
                onMakeDefault = { id ->
                    if (services.environment.backendConfigured) {
                        accountDataBusy = true; accountDataError = null
                        appScope.launch {
                            runCatching { accountData.makeDefault(id) }
                                .onSuccess { paymentMethods = it; accountDataBusy = false }
                                .onFailure { accountDataError = it.localizedMessage; accountDataBusy = false }
                        }
                    }
                },
                onRemove = { id ->
                    if (services.environment.backendConfigured) {
                        accountDataBusy = true; accountDataError = null
                        appScope.launch {
                            runCatching { accountData.removePaymentMethod(id) }
                                .onSuccess { paymentMethods = it; accountDataBusy = false }
                                .onFailure { accountDataError = it.localizedMessage; accountDataBusy = false }
                        }
                    }
                }
            )
        }
        composable(Routes.SAVED_PLACES) {
            SavedPlacesScreen(
                home = savedHome,
                work = savedWork,
                syncing = accountDataBusy,
                errorMessage = accountDataError,
                onBack = { nav.popBackStack() },
                onEdit = { slot ->
                    savePlaceTarget = slot
                    nav.navigate(Routes.SEARCH)
                },
                onClear = { slot ->
                    localStore.clearSavedPlace(slot)
                    if (slot == "home") savedHome = null else savedWork = null
                    if (services.environment.backendConfigured && signedIn) appScope.launch {
                        runCatching { accountData.removePlace(slot) }
                            .onSuccess { accountDataError = null }
                            .onFailure { accountDataError = it.localizedMessage ?: "Could not remove saved place" }
                    }
                }
            )
        }
        composable(Routes.SAFETY) { AccountDetailScreen("Safety", "Ride PIN, trip sharing, emergency assistance and support shortcuts will be available here.") { nav.popBackStack() } }
        composable(Routes.LANGUAGE) { LanguageScreen { nav.popBackStack() } }
        composable(Routes.HELP) { AccountDetailScreen("Help & legal", "Support, trip issues, terms, privacy and accessibility information will be organized here.") { nav.popBackStack() } }
        composable(Routes.APPEARANCE) {
            AppearanceScreen(
                themeMode = themeMode,
                onThemeModeChange = onThemeModeChange,
                onBack = { nav.popBackStack() }
            )
        }
        }
        completionPrompt?.let { tripId ->
            trips.firstOrNull { it.id == tripId }?.let { trip ->
                PostTripExperienceSheet(trip, repository, onDismiss = { completionPrompt = null })
            }
        }
    }
}

@Composable
private fun PostTripExperienceSheet(trip: RideTrip, repository: RideNovaRepository, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var stars by rememberSaveable(trip.id) { mutableIntStateOf(5) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var supportOpen by remember { mutableStateOf(false) }
    ModalBottomSheet(onDismissRequest = onDismiss, dragHandle = { BottomSheetDefaults.DragHandle() }) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 22.dp, vertical = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Icon(Icons.Default.CheckCircle, null, Modifier.size(42.dp), tint = NovaSuccess)
            Text("Ride complete", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text("How was your driver?", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
                (1..5).forEach { value -> IconButton(onClick = { stars = value }, enabled = !busy) {
                    Icon(if (value <= stars) Icons.Default.Star else Icons.Default.StarBorder,
                        "$value stars", tint = Color(0xFFFFB000), modifier = Modifier.size(32.dp))
                } }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            Button(enabled = !busy, onClick = {
                busy = true; error = null
                scope.launch {
                    runCatching { repository.rateRide(trip.id, stars, emptyList(), "") }
                        .onSuccess { onDismiss() }
                        .onFailure { error = it.localizedMessage ?: "Could not save rating" }
                    busy = false
                }
            }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) {
                Text(if (busy) "Saving…" else "Submit driver rating")
            }
            OutlinedButton(onClick = { supportOpen = true }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Shield, null); Spacer(Modifier.width(8.dp)); Text("Safety or trip support")
            }
            TextButton(onClick = onDismiss) { Text("Not now") }
        }
    }
    if (supportOpen) PassengerSupportDialog(onDismiss = { supportOpen = false }) { category, description ->
        scope.launch {
            busy = true; error = null
            runCatching { repository.createSupportCase(trip.id, category, description) }
                .onSuccess { supportOpen = false; onDismiss() }
                .onFailure { error = it.localizedMessage ?: "Could not create support case" }
            busy = false
        }
    }
}

@Composable
private fun SplashScreen(onDone: () -> Unit) {
    LaunchedEffect(Unit) { delay(950); onDone() }
    Box(
        Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(NovaMidnight, NovaNavy))),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            NovaMark(82)
            Spacer(Modifier.height(20.dp))
            Text("RideNova", color = Color.White, fontSize = 38.sp, fontWeight = FontWeight.Bold)
            Text(stringResource(R.string.tagline), color = Color.White.copy(alpha = .75f), fontSize = 16.sp)
        }
    }
}

@Composable
private fun NovaMark(size: Int = 56) {
    Box(
        Modifier.size(size.dp).clip(RoundedCornerShape((size * .28).dp))
            .background(Brush.linearGradient(listOf(NovaBlue, NovaViolet))),
        contentAlignment = Alignment.Center
    ) {
        Text("R", color = Color.White, fontSize = (size * .52).sp, fontWeight = FontWeight.Black)
        Text("✦", color = Color.White, fontSize = (size * .22).sp, modifier = Modifier.align(Alignment.TopEnd).padding(5.dp))
    }
}

@Composable
private fun WelcomeScreen(onStart: () -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .safeDrawingPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 28.dp, vertical = 24.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        Column {
            Spacer(Modifier.height(18.dp))
            NovaMark()
            Spacer(Modifier.height(20.dp))
            Text(
                "Your city. Your ride.",
                fontSize = 36.sp,
                lineHeight = 40.sp,
                fontWeight = FontWeight.Black,
                color = MaterialTheme.colorScheme.onSurface
            )
            Spacer(Modifier.height(12.dp))
            Text(
                "A premium, transparent ride experience designed around safety and trust.",
                fontSize = 18.sp,
                lineHeight = 26.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(18.dp))
            RideNovaHeroIllustration()
            Spacer(Modifier.height(14.dp))
            Surface(
                shape = RoundedCornerShape(50),
                color = MaterialTheme.colorScheme.surfaceVariant
            ) {
                Row(
                    Modifier.padding(horizontal = 14.dp, vertical = 9.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("🇨🇦", fontSize = 18.sp)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "Built in Canada. Made to move everyone.",
                        color = MaterialTheme.colorScheme.onSurface,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }

        Column {
            FeatureRow(Icons.Default.VerifiedUser, "Safety-first experience")
            FeatureRow(Icons.Default.Payments, "Clear upfront pricing")
            FeatureRow(Icons.Default.Language, "English · Français · Español")
            Spacer(Modifier.height(16.dp))
            PrimaryButton("Continue with phone", onStart)
            Text(
                "New riders create an account; returning riders sign in with the same phone number.",
                modifier = Modifier.fillMaxWidth().padding(top = 9.dp),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontSize = 11.sp
            )
        }
    }
}

@Composable
private fun RideNovaHeroIllustration() {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .height(170.dp),
        shape = RoundedCornerShape(30.dp),
        color = MaterialTheme.colorScheme.surfaceVariant
    ) {
        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.linearGradient(
                        listOf(
                            NovaBlue.copy(alpha = .16f),
                            MaterialTheme.colorScheme.surfaceVariant,
                            NovaViolet.copy(alpha = .14f)
                        )
                    )
                )
                .padding(18.dp)
        ) {
            // Soft city blocks keep the illustration visual without tying RideNova to one city.
            Row(
                Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.Bottom
            ) {
                listOf(42, 66, 52, 82, 48, 72, 38).forEachIndexed { index, height ->
                    Box(
                        Modifier
                            .width(if (index % 2 == 0) 24.dp else 30.dp)
                            .height(height.dp)
                            .clip(RoundedCornerShape(topStart = 7.dp, topEnd = 7.dp))
                            .background(NovaMidnight.copy(alpha = .07f))
                    )
                }
            }

            // Route corridor. The individual segments give the hero a sense of movement.
            Box(
                Modifier
                    .width(150.dp)
                    .height(10.dp)
                    .align(Alignment.Center)
                    .offset(x = (-28).dp, y = 4.dp)
                    .clip(RoundedCornerShape(50))
                    .background(Brush.horizontalGradient(listOf(NovaBlue, NovaViolet)))
            )
            Box(
                Modifier
                    .width(10.dp)
                    .height(76.dp)
                    .align(Alignment.Center)
                    .offset(x = 43.dp, y = (-28).dp)
                    .clip(RoundedCornerShape(50))
                    .background(NovaViolet)
            )

            Surface(
                modifier = Modifier
                    .align(Alignment.CenterStart)
                    .offset(x = 12.dp, y = 4.dp),
                shape = CircleShape,
                color = Color.White,
                shadowElevation = 5.dp
            ) {
                Icon(
                    Icons.Default.MyLocation,
                    contentDescription = "Pickup",
                    tint = NovaBlue,
                    modifier = Modifier.padding(10.dp)
                )
            }

            Surface(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .offset(x = (-20).dp, y = 18.dp),
                shape = CircleShape,
                color = Color.White,
                shadowElevation = 5.dp
            ) {
                Icon(
                    Icons.Default.Place,
                    contentDescription = "Destination",
                    tint = NovaViolet,
                    modifier = Modifier.padding(10.dp)
                )
            }

            // Keep the hero visual simple and high-contrast in both themes. A compact
            // vehicle badge reads as movement at a glance without a dense text card.
            Box(
                modifier = Modifier
                    .align(Alignment.Center)
                    .offset(x = 10.dp, y = 2.dp)
                    .size(74.dp)
                    .clip(CircleShape)
                    .background(Brush.linearGradient(listOf(NovaBlue, NovaViolet))),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Default.DirectionsCar,
                    contentDescription = "RideNova car",
                    tint = Color.White,
                    modifier = Modifier.size(34.dp)
                )
            }

            Text(
                "A smarter way to move",
                modifier = Modifier.align(Alignment.TopStart),
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold
            )
        }
    }
}

@Composable
private fun FeatureRow(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Row(Modifier.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = NovaBlue); Spacer(Modifier.width(12.dp)); Text(text, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun PhoneScreen(initialPhone: String, busy: Boolean, errorMessage: String?, backendMode: Boolean, onBack: () -> Unit, onContinue: (String) -> Unit) {
    var phone by remember { mutableStateOf(initialPhone.filter(Char::isDigit).takeLast(10)) }
    FormScaffold(title = stringResource(R.string.phone_title), subtitle = "We’ll send a verification code to confirm it’s you.") {
        TextButton(onClick = onBack, enabled = !busy) { Icon(Icons.Default.ArrowBack, "Back"); Spacer(Modifier.width(6.dp)); Text("Back") }
        OutlinedTextField(phone, { phone = it.filter(Char::isDigit).take(10) }, modifier = Modifier.fillMaxWidth(),
            label = { Text("Canadian mobile number") }, prefix = { Text("+1  ") },
            supportingText = { Text("10 digits · standard messaging may apply when SMS is connected") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone), singleLine = true, enabled = !busy)
        errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 10.dp)) }
        Spacer(Modifier.height(16.dp)); PrimaryButton(if (busy) "Requesting code…" else "Send verification code", { onContinue("+1$phone") }, enabled = phone.length == 10 && !busy)
        Spacer(Modifier.height(16.dp)); Text(if (backendMode) "Development authentication: the code will appear on the next screen. No SMS is sent." else "Offline prototype: use code 123456.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
    }
}

@Composable
private fun OtpScreen(phone: String, developmentCode: String?, busy: Boolean, errorMessage: String?, onBack: () -> Unit, onVerified: (String) -> Unit) {
    var otp by remember { mutableStateOf("") }
    FormScaffold(title = stringResource(R.string.otp_title), subtitle = "Enter the six-digit code for $phone.") {
        if (BuildConfig.RIDENOVA_ENVIRONMENT == "staging") {
            Text("Staging test: use the code provided with your invitation. No SMS is sent.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        TextButton(onClick = onBack, enabled = !busy) { Icon(Icons.Default.ArrowBack, "Back"); Spacer(Modifier.width(6.dp)); Text("Change number") }
        developmentCode?.let {
            Surface(shape = RoundedCornerShape(16.dp), color = NovaBlue.copy(alpha = .10f)) {
                Text("Development code: $it", modifier = Modifier.fillMaxWidth().padding(14.dp), fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(12.dp))
        }
        OutlinedTextField(otp, { otp = it.filter(Char::isDigit).take(6) }, modifier = Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.otp_hint)) }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true, enabled = !busy)
        errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 10.dp)) }
        Spacer(Modifier.height(16.dp)); PrimaryButton(if (busy) "Verifying…" else "Verify", { onVerified(otp) }, enabled = otp.length == 6 && !busy)
        Spacer(Modifier.height(12.dp)); Text("The code expires after five minutes. Return to the phone screen to request another code.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
    }
}

@Composable
private fun ProfileScreen(initial: RiderProfile?, phone: String, busy: Boolean, errorMessage: String?, title: String = "Complete your profile", buttonLabel: String = "Continue", onBack: (() -> Unit)? = null, onDone: (RiderProfile) -> Unit) {
    var first by remember(initial) { mutableStateOf(initial?.firstName.orEmpty()) }
    var last by remember(initial) { mutableStateOf(initial?.lastName.orEmpty()) }
    var email by remember(initial) { mutableStateOf(initial?.email.orEmpty()) }
    val emailValid = email.isBlank() || android.util.Patterns.EMAIL_ADDRESS.matcher(email.trim()).matches()
    FormScaffold(title = title, subtitle = "Your name identifies your passenger account. A profile photo can be added later.") {
        onBack?.let { TextButton(onClick = it, enabled = !busy) { Icon(Icons.Default.ArrowBack, "Back"); Spacer(Modifier.width(6.dp)); Text("Back") } }
        Box(Modifier.size(82.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surfaceVariant).align(Alignment.CenterHorizontally), contentAlignment = Alignment.Center) { Icon(Icons.Default.Person, null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(40.dp)) }
        Spacer(Modifier.height(18.dp))
        OutlinedTextField(first, { first = it.take(80) }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.first_name)) }, singleLine = true, enabled = !busy)
        Spacer(Modifier.height(10.dp)); OutlinedTextField(last, { last = it.take(80) }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.last_name)) }, singleLine = true, enabled = !busy)
        Spacer(Modifier.height(10.dp)); OutlinedTextField(email, { email = it.take(254) }, Modifier.fillMaxWidth(), label = { Text("Email (optional)") }, isError = !emailValid, supportingText = { if (!emailValid) Text("Enter a valid email or leave it blank") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email), singleLine = true, enabled = !busy)
        if (phone.isNotBlank()) { Spacer(Modifier.height(10.dp)); Text("Account phone: $phone", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 10.dp)) }
        Spacer(Modifier.height(18.dp)); PrimaryButton(if (busy) "Saving…" else buttonLabel, { onDone(RiderProfile(first.trim(), last.trim(), email.trim(), phone)) }, enabled = first.isNotBlank() && last.isNotBlank() && emailValid && !busy)
    }
}

@Composable
private fun FormScaffold(title: String, subtitle: String, content: @Composable ColumnScope.() -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .safeDrawingPadding()
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(26.dp)
    ) {
        Spacer(Modifier.height(36.dp)); NovaMark(48); Spacer(Modifier.height(30.dp))
        Text(title, fontSize = 28.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onBackground)
        Spacer(Modifier.height(8.dp)); Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(28.dp)); content()
        Spacer(Modifier.height(28.dp))
    }
}

@Composable
private fun HomeScreen(
    nav: NavHostController,
    recentDestinations: List<PlaceSuggestion>,
    savedHome: PlaceSuggestion?,
    savedWork: PlaceSuggestion?,
    activeTrip: RideTrip?,
    onResumeTrip: (RideTrip) -> Unit,
    onSearchDestination: () -> Unit,
    onSavedPlace: (PlaceSuggestion?) -> Unit,
    onRecentDestination: (PlaceSuggestion) -> Unit,
    onPickupResolved: (Double, Double, String?) -> Unit
) {
    val homeDensity = LocalDensity.current
    var homeCardHeight by remember { mutableStateOf(0.dp) }
    Scaffold(
        bottomBar = { BottomBar(nav = nav, selectedRoute = Routes.HOME) }
    ) { pad ->
        BoxWithConstraints(Modifier.fillMaxSize().padding(pad)) {
            val cardLimit = maxHeight * 0.68f
            RideNovaMap(modifier = Modifier.fillMaxSize(), bottomContentPadding = homeCardHeight + 24.dp, onLocationResolved = { point, address -> onPickupResolved(point.latitude, point.longitude, address) })
            Column(Modifier.align(Alignment.TopStart).padding(18.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) { NovaMark(42); Spacer(Modifier.width(10.dp)); Text("RideNova", fontWeight = FontWeight.Bold, fontSize = 22.sp, color = MaterialTheme.colorScheme.onSurface) }
            }
            Card(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(16.dp).onSizeChanged { homeCardHeight = with(homeDensity) { it.height.toDp() } },
                shape = RoundedCornerShape(28.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
            ) {
                Column(Modifier.heightIn(max = cardLimit).verticalScroll(rememberScrollState()).padding(18.dp)) {
                    Text("Good to see you", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("Where can we take you?", fontSize = 24.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                    Spacer(Modifier.height(16.dp))
                    Surface(Modifier.fillMaxWidth().clickable(onClick = onSearchDestination), shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                        Row(Modifier.padding(17.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Search, null); Spacer(Modifier.width(12.dp)); Text(stringResource(R.string.where_to), fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
                        }
                    }
                    if (activeTrip != null) {
                        Spacer(Modifier.height(12.dp))
                        Surface(
                            Modifier.fillMaxWidth().clickable { onResumeTrip(activeTrip) },
                            shape = RoundedCornerShape(18.dp),
                            color = NovaBlue.copy(alpha = .10f)
                        ) {
                            Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.DirectionsCar, null, tint = NovaBlue)
                                Spacer(Modifier.width(10.dp))
                                Column(Modifier.weight(1f)) {
                                    Text("${if (activeTrip.status in liveTripStatuses) "Active ride" else "Past ride"} · ${tripStatusLabel(activeTrip.status)}", fontWeight = FontWeight.SemiBold)
                                    Text(activeTrip.draft.destination?.name ?: "RideNova trip", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                                }
                                Text("View", color = NovaBlue, fontWeight = FontWeight.SemiBold)
                            }
                        }
                    }
                    Spacer(Modifier.height(14.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        QuickPlace("Home", savedHome?.name ?: "Set home", Icons.Default.Home, Modifier.weight(1f)) { onSavedPlace(savedHome) }
                        QuickPlace("Work", savedWork?.name ?: "Set work", Icons.Default.Work, Modifier.weight(1f)) { onSavedPlace(savedWork) }
                    }
                    if (recentDestinations.isNotEmpty()) {
                        Spacer(Modifier.height(15.dp))
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text("Recent", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        }
                        recentDestinations.take(1).forEach { place ->
                            Row(
                                Modifier.fillMaxWidth().clickable { onRecentDestination(place) }.padding(vertical = 9.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Box(Modifier.size(36.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
                                    Icon(Icons.Default.History, null, tint = NovaBlue, modifier = Modifier.size(19.dp))
                                }
                                Spacer(Modifier.width(10.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(place.name, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                    Text(place.address, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                }
                                Icon(Icons.Default.ChevronRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun QuickPlace(
    text: String,
    subtitle: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    modifier: Modifier,
    onClick: () -> Unit
) {
    Surface(modifier.clickable(onClick = onClick), shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, tint = NovaBlue)
            Spacer(Modifier.width(8.dp))
            Column(Modifier.weight(1f)) {
                Text(text, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

@Composable
private fun SearchScreen(
    recentDestinations: List<PlaceSuggestion>,
    screenTitle: String,
    searchHint: String,
    onBack: () -> Unit,
    onPlace: (PlaceSuggestion) -> Unit,
    onClearRecent: () -> Unit,
    onRemoveRecent: (PlaceSuggestion) -> Unit
) {
    val context = LocalContext.current
    val livePlacesEnabled = googleMapsConfigured() && Places.isInitialized()
    val placesClient = remember(livePlacesEnabled) { if (livePlacesEnabled) Places.createClient(context) else null }
    var query by remember { mutableStateOf("") }
    val latestQuery by rememberUpdatedState(query.trim())
    var searchGeneration by remember { mutableIntStateOf(0) }
    var predictions by remember { mutableStateOf<List<AutocompletePrediction>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var searchError by remember { mutableStateOf<String?>(null) }

    val demoFiltered = DemoData.places.filter {
        query.isBlank() || it.name.contains(query, true) || it.address.contains(query, true)
    }

    LaunchedEffect(query, livePlacesEnabled) {
        searchError = null
        predictions = emptyList()
        loading = false
        val generation = ++searchGeneration
        val requestedQuery = query.trim()
        if (!livePlacesEnabled || query.trim().length < 2) {
            predictions = emptyList()
            loading = false
            return@LaunchedEffect
        }
        loading = true
        delay(280)
        if (query.trim().length < 2) return@LaunchedEffect
        loading = true
        val request = FindAutocompletePredictionsRequest.builder()
            .setQuery(query.trim())
            .setCountries(listOf("CA"))
            .setRegionCode("CA")
            .build()
        placesClient?.findAutocompletePredictions(request)
            ?.addOnSuccessListener { response ->
                if (generation != searchGeneration || requestedQuery != latestQuery) return@addOnSuccessListener
                predictions = response.autocompletePredictions
                loading = false
            }
            ?.addOnFailureListener { error ->
                if (generation != searchGeneration || requestedQuery != latestQuery) return@addOnFailureListener
                searchError = error.localizedMessage ?: "Place search unavailable"
                loading = false
            }
    }

    fun choosePrediction(prediction: AutocompletePrediction) {
        val client = placesClient ?: return
        loading = true
        val request = FetchPlaceRequest.newInstance(
            prediction.placeId,
            listOf(Place.Field.ID, Place.Field.DISPLAY_NAME, Place.Field.FORMATTED_ADDRESS, Place.Field.LOCATION)
        )
        client.fetchPlace(request)
            .addOnSuccessListener { response ->
                val place = response.place
                val location = place.location
                onPlace(
                    PlaceSuggestion(
                        name = place.displayName ?: prediction.getPrimaryText(null).toString(),
                        address = place.formattedAddress ?: prediction.getSecondaryText(null).toString(),
                        latitude = location?.latitude,
                        longitude = location?.longitude,
                        placeId = place.id ?: prediction.placeId
                    )
                )
                loading = false
            }
            .addOnFailureListener { error ->
                searchError = error.localizedMessage ?: "Could not load this destination"
                loading = false
            }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(screenTitle) },
                navigationIcon = { IconButton(onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { pad ->
        Column(Modifier.padding(pad).consumeWindowInsets(pad).imePadding().fillMaxSize().padding(horizontal = 18.dp)) {
            OutlinedTextField(
                query,
                { query = it },
                Modifier.fillMaxWidth(),
                leadingIcon = { Icon(Icons.Default.Search, null) },
                placeholder = { Text(searchHint) },
                trailingIcon = { if (query.isNotEmpty()) IconButton({ query = "" }) { Icon(Icons.Default.Close, "Clear search") } },
                singleLine = true,
                shape = RoundedCornerShape(18.dp)
            )
            Spacer(Modifier.height(10.dp))

            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
                if (query.isBlank() && recentDestinations.isNotEmpty()) {
                    Row(Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text("Recent destinations", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                        TextButton(onClick = onClearRecent) { Text("Clear") }
                    }
                    // Expanded search shows up to five unique recent destinations.
                    // The home screen independently shows only one.
                    recentDestinations
                        .distinctBy { it.address.trim().lowercase() }
                        .take(5)
                        .forEach { place ->
                        Row(
                            Modifier.fillMaxWidth().clickable { onPlace(place) }.padding(vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Box(Modifier.size(42.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
                                Icon(Icons.Default.History, null, tint = NovaBlue)
                            }
                            Spacer(Modifier.width(12.dp))
                            Column(Modifier.weight(1f)) {
                                Text(place.name, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text(place.address, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            }
                            IconButton(onClick = { onRemoveRecent(place) }) {
                                Icon(Icons.Default.Close, contentDescription = "Remove recent destination", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                    }
                    Spacer(Modifier.height(12.dp))
                }

                if (livePlacesEnabled) {
                    Text("Live Google Places · Canada", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                    if (loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 10.dp))
                    searchError?.let {
                        Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp, modifier = Modifier.padding(top = 8.dp))
                    }
                    Spacer(Modifier.height(8.dp))
                    if (!loading && searchError == null && query.trim().length >= 2 && predictions.isEmpty())
                        Text("No places found. Try a street address or nearby landmark.", Modifier.padding(vertical = 16.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    predictions.forEach { prediction ->
                        Row(
                            Modifier.fillMaxWidth().clickable { choosePrediction(prediction) }.padding(vertical = 13.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Box(Modifier.size(42.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
                                Icon(Icons.Default.LocationOn, null, tint = NovaBlue)
                            }
                            Spacer(Modifier.width(12.dp))
                            Column(Modifier.weight(1f)) {
                                Text(prediction.getPrimaryText(null).toString(), fontWeight = FontWeight.SemiBold)
                                Text(prediction.getSecondaryText(null).toString(), color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                            }
                        }
                        HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                    }
                    if (query.length < 2 && recentDestinations.isEmpty()) {
                        Text("Start typing a destination. Your recent searches will appear here next time.", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 20.dp))
                    }
                } else {
                    Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                        Column(Modifier.fillMaxWidth().padding(14.dp)) {
                            Text("Google Places is ready to connect", fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                            Text("Add MAPS_API_KEY to local.properties. Until then these sample BC destinations keep the booking flow testable.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    demoFiltered.forEach { place ->
                        Row(Modifier.fillMaxWidth().clickable { onPlace(place) }.padding(vertical = 13.dp), verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(42.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) { Icon(Icons.Default.LocationOn, null, tint = NovaBlue) }
                            Spacer(Modifier.width(12.dp))
                            Column { Text(place.name, fontWeight = FontWeight.SemiBold); Text(place.address, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp) }
                        }
                        HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                    }
                }
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}

@Composable
private fun RideSelectionScreen(
    draft: BookingDraft,
    onBack: () -> Unit,
    onSelect: (RideTier) -> Unit,
    onRouteSelected: (RouteEstimate) -> Unit,
    onSchedule: () -> Unit,
    onContinue: () -> Unit
) {
    val context = LocalContext.current
    val density = LocalDensity.current
    val coroutineScope = rememberCoroutineScope()
    val fallbackEstimate = remember(draft.pickup, draft.destination) {
        FareEstimator.route(draft.pickup, draft.destination)
    }
    var routeChoices by remember(draft.pickup, draft.destination) { mutableStateOf<RouteChoices?>(null) }
    var selectedRouteType by remember(draft.pickup, draft.destination) { mutableStateOf(RouteType.BEST) }
    var routeEstimate by remember(draft.pickup, draft.destination) { mutableStateOf(draft.routeEstimate ?: fallbackEstimate) }
    var routeLoading by remember(draft.pickup, draft.destination) { mutableStateOf(false) }
    var routeError by remember(draft.pickup, draft.destination) { mutableStateOf<String?>(null) }

    LaunchedEffect(draft.pickup, draft.destination) {
        val destination = draft.destination
        if (draft.pickup.latitude != null && draft.pickup.longitude != null &&
            destination?.latitude != null && destination.longitude != null && googleMapsConfigured()
        ) {
            routeLoading = true
            routeError = null
            GoogleRoutesService.computeDrivingRoutes(context, draft.pickup, destination)
                .onSuccess { choices ->
                    routeChoices = choices
                    val recommended = choices.best ?: choices.fastest
                    selectedRouteType = RouteType.BEST
                    routeEstimate = recommended
                    onRouteSelected(recommended)
                }
                .onFailure {
                    routeChoices = null
                    routeEstimate = fallbackEstimate
                    fallbackEstimate?.let(onRouteSelected)
                    routeError = "Smart road route unavailable — showing an approximate estimate."
                }
            routeLoading = false
        }
    }

    fun chooseRoute(type: RouteType) {
        val chosen = when (type) {
            RouteType.BEST -> routeChoices?.best ?: routeChoices?.fastest
            RouteType.FASTEST -> routeChoices?.fastest
            RouteType.SHORTEST -> routeChoices?.shortest
            RouteType.POCKET -> routeChoices?.pocketFriendly
            RouteType.ALTERNATIVE -> routeChoices?.alternatives?.firstOrNull()
        } ?: return
        selectedRouteType = type
        routeEstimate = chosen
        onRouteSelected(chosen)
    }

    val rideOptions = remember(routeEstimate) { FareEstimator.rideOptions(routeEstimate) }
    val selectedOption = rideOptions.firstOrNull { it.tier == draft.selectedTier } ?: rideOptions.first()
    val bottomSheetState = rememberStandardBottomSheetState(
        initialValue = SheetValue.PartiallyExpanded,
        skipHiddenState = true
    )
    val scaffoldState = rememberBottomSheetScaffoldState(bottomSheetState = bottomSheetState)

    BoxWithConstraints(Modifier.fillMaxSize()) {
        val sheetPeekHeight = 400.dp
        val sheetMaxHeight = (maxHeight - 28.dp).coerceAtLeast(300.dp)

        // Build 32: do not read requireOffset() in composition while the sheet is being dragged.
        // That offset changes every frame and previously forced the large route/map subtree to
        // recompose continuously. A stable map inset lets Material 3 own the drag animation.
        BottomSheetScaffold(
            scaffoldState = scaffoldState,
            sheetPeekHeight = sheetPeekHeight,
            sheetContainerColor = MaterialTheme.colorScheme.surface,
            sheetContent = {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .heightIn(max = sheetMaxHeight)
                        .verticalScroll(rememberScrollState())
                        .navigationBarsPadding()
                        .padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 96.dp)
                ) {
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text("Choose your ride", fontSize = 22.sp, fontWeight = FontWeight.Bold)
                            routeEstimate?.let { route ->
                                Text(
                                    "${"%.1f".format(route.distanceKm)} km · ${route.durationMinutes} min",
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    fontSize = 13.sp
                                )
                            }
                        }
                        TextButton(onClick = { coroutineScope.launch { bottomSheetState.expand() } }) {
                            Text("All options")
                            Icon(Icons.Default.KeyboardArrowUp, null)
                        }
                    }

                    routeChoices?.let { choices ->
                        val routeButtons = buildList {
                            val best = choices.best ?: choices.fastest
                            add(Triple(RouteType.BEST, best, "Best match"))

                            // Let live traffic, not the clock, decide whether extra choices are useful.
                            // At quiet times these thresholds naturally collapse the UI to Best match.
                            val fastestTimeSaving = best.durationMinutes - choices.fastest.durationMinutes
                            val fastestPercentSaving = fastestTimeSaving.toDouble() / best.durationMinutes.coerceAtLeast(1)
                            if (!sameRoute(choices.fastest, best) &&
                                (fastestTimeSaving >= 2 || fastestPercentSaving >= 0.06)
                            ) {
                                add(Triple(RouteType.FASTEST, choices.fastest, "Fastest"))
                            }

                            choices.shortest?.takeIf { shortest ->
                                val kmSaving = best.distanceKm - shortest.distanceKm
                                !sameRoute(shortest, best) && kmSaving >= 0.5
                            }?.let { add(Triple(RouteType.SHORTEST, it, "Shortest")) }

                            choices.pocketFriendly?.takeIf { candidate ->
                                val bestFare = FareEstimator.rideOptions(best).first().fareCad
                                val saverFare = FareEstimator.rideOptions(candidate).first().fareCad
                                val fareSaving = bestFare - saverFare
                                all { !sameRoute(it.second, candidate) } && fareSaving >= 1.50
                            }?.let { add(Triple(RouteType.POCKET, it, "Saver")) }
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            routeButtons.forEach { (type, route, label) ->
                                val chipText = when (type) {
                                    RouteType.BEST -> "$label · ${route.durationMinutes} min"
                                    RouteType.FASTEST -> "$label · ${route.durationMinutes} min"
                                    RouteType.SHORTEST -> "$label · ${"%.1f".format(route.distanceKm)} km"
                                    RouteType.POCKET -> "$label · \$${"%.0f".format(FareEstimator.rideOptions(route).first().fareCad)}"
                                    RouteType.ALTERNATIVE -> label
                                }
                                FilterChip(
                                    selected = selectedRouteType == type ||
                                        (selectedRouteType == RouteType.FASTEST && type == RouteType.BEST && sameRoute(route, choices.fastest)),
                                    onClick = { chooseRoute(type) },
                                    label = { Text(chipText) },
                                    leadingIcon = if (selectedRouteType == type) {
                                        {
                                            Icon(
                                                when (type) {
                                                    RouteType.BEST -> Icons.Default.AutoAwesome
                                                    RouteType.FASTEST -> Icons.Default.Bolt
                                                    RouteType.SHORTEST -> Icons.Default.Straighten
                                                    RouteType.POCKET -> Icons.Default.Savings
                                                    RouteType.ALTERNATIVE -> Icons.Default.Route
                                                },
                                                null,
                                                Modifier.size(16.dp)
                                            )
                                        }
                                    } else null
                                )
                            }
                        }
                        Spacer(Modifier.height(4.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            if (routeButtons.size == 1) {
                                Icon(
                                    Icons.Default.CheckCircle,
                                    contentDescription = null,
                                    modifier = Modifier.size(15.dp),
                                    tint = NovaSuccess
                                )
                                Spacer(Modifier.width(6.dp))
                            }
                            Text(
                                if (routeButtons.size == 1) {
                                    "Best match is already the fastest practical route right now."
                                } else {
                                    when (selectedRouteType) {
                                        RouteType.BEST -> "Recommended balance of live ETA, distance and estimated fare."
                                        RouteType.FASTEST -> "Prioritizes the lowest live-traffic ETA."
                                        RouteType.SHORTEST -> "Prioritizes fewer kilometres."
                                        RouteType.POCKET -> "Prioritizes the lowest estimated Economy fare."
                                        RouteType.ALTERNATIVE -> "Alternative road route."
                                    }
                                },
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 11.sp
                            )
                        }
                    }

                    Spacer(Modifier.height(10.dp))
                    Text(
                        "Ride options",
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    rideOptions.forEach { option ->
                        RideCard(
                            option = option,
                            selected = option.tier == selectedOption.tier,
                            onClick = { onSelect(option.tier) }
                        )
                    }

                    routeError?.let {
                        Spacer(Modifier.height(6.dp))
                        Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                    }
                    Spacer(Modifier.height(8.dp))
                    Text(
                        if (routeEstimate?.isApproximate == false)
                            "Traffic-aware routing is live. Final RideNova pricing will be calculated by the backend."
                        else
                            "Approximate prototype estimate only. Final routing and pricing will be server-authoritative.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                    Spacer(Modifier.height(8.dp))
                }
            }
        ) {
            Box(Modifier.fillMaxSize()) {
                RideNovaMap(
                    modifier = Modifier.fillMaxSize(),
                    pickup = draft.pickup,
                    destination = draft.destination,
                    routePoints = routeEstimate?.path.orEmpty(),
                    compact = true,
                    bottomContentPadding = sheetPeekHeight,
                    animateRoute = routeEstimate?.path?.size?.let { it > 1 } == true
                )

                Surface(
                    onClick = onBack,
                    modifier = Modifier
                        .statusBarsPadding()
                        .padding(start = 16.dp, top = 10.dp)
                        .size(52.dp)
                        .align(Alignment.TopStart),
                    shape = CircleShape,
                    color = MaterialTheme.colorScheme.surface.copy(alpha = .94f),
                    shadowElevation = 8.dp
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }

                RouteAddressOverlay(
                    pickupAddress = draft.pickup.address.ifBlank { "Current location" },
                    destinationAddress = draft.destination?.address ?: draft.destination?.name.orEmpty(),
                    modifier = Modifier
                        .statusBarsPadding()
                        .align(Alignment.TopCenter)
                        .padding(top = 10.dp, start = 82.dp, end = 14.dp)
                )

                if (routeLoading) {
                    Surface(
                        modifier = Modifier
                            .align(Alignment.TopCenter)
                            .statusBarsPadding()
                            .padding(top = 116.dp),
                        shape = RoundedCornerShape(20.dp),
                        color = MaterialTheme.colorScheme.surface.copy(alpha = .94f),
                        shadowElevation = 5.dp
                    ) {
                        Row(
                            Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            CircularProgressIndicator(Modifier.size(17.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                            Text("Optimizing route with live traffic…", fontSize = 12.sp)
                        }
                    }
                }
            }
        }

        Surface(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth(),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 8.dp,
            shadowElevation = 12.dp
        ) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                OutlinedButton(
                    onClick = onSchedule,
                    modifier = Modifier.weight(1f).heightIn(min = 56.dp),
                    shape = RoundedCornerShape(17.dp)
                ) {
                    Icon(Icons.Default.CalendarMonth, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text(if (draft.scheduled) "Scheduled" else "Schedule")
                }
                Button(
                    onClick = onContinue,
                    modifier = Modifier.weight(1f).heightIn(min = 56.dp),
                    shape = RoundedCornerShape(17.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primary,
                        contentColor = MaterialTheme.colorScheme.onPrimary
                    )
                ) {
                    Text("Choose ${selectedOption.title}", fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                }
            }
        }
    }
}

private fun sameRoute(a: RouteEstimate?, b: RouteEstimate?): Boolean {
    if (a == null || b == null) return false
    return kotlin.math.abs(a.distanceKm - b.distanceKm) < 0.15 &&
        kotlin.math.abs(a.durationMinutes - b.durationMinutes) <= 1
}

@Composable
private fun RouteAddressOverlay(
    pickupAddress: String,
    destinationAddress: String,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = .94f),
        shadowElevation = 7.dp
    ) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 9.dp)) {
            AddressLine(color = NovaSuccess, label = "Pickup", address = pickupAddress)
            Spacer(Modifier.height(5.dp))
            AddressLine(color = NovaBlue, label = "Destination", address = destinationAddress)
        }
    }
}

@Composable
private fun AddressLine(color: Color, label: String, address: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(9.dp).clip(CircleShape).background(color))
        Spacer(Modifier.width(8.dp))
        Text(
            "$label · $address",
            modifier = Modifier.weight(1f),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            fontSize = 12.sp,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
private fun RideCard(option: RideOption, selected: Boolean, onClick: () -> Unit) {
    val border = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline.copy(alpha = .18f)
    Card(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(18.dp),
        border = androidx.compose.foundation.BorderStroke(if (selected) 1.8.dp else 1.dp, border),
        colors = CardDefaults.cardColors(
            containerColor = if (selected) MaterialTheme.colorScheme.primary.copy(alpha = .08f)
            else MaterialTheme.colorScheme.surface
        )
    ) {
        Row(Modifier.padding(horizontal = 14.dp, vertical = 13.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(54.dp).clip(RoundedCornerShape(15.dp)).background(MaterialTheme.colorScheme.surfaceVariant),
                contentAlignment = Alignment.Center
            ) {
                Icon(Icons.Default.DirectionsCar, null, tint = MaterialTheme.colorScheme.onSurface)
            }
            Spacer(Modifier.width(13.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(option.title, fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
                    if (selected) {
                        Spacer(Modifier.width(7.dp))
                        Icon(Icons.Default.CheckCircle, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(17.dp))
                    }
                }
                Text("${option.etaMinutes} min · ${option.seats} seats", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                Text(option.description, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Spacer(Modifier.width(10.dp))
            Text("$${"%.2f".format(option.fareCad)}", fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
        }
    }
}

@Composable
private fun ScheduleScreen(initialPickup: Long?, onBack: () -> Unit, onChoose: (Long?, String?) -> Unit) {
    val context = LocalContext.current
    val zone = remember { java.time.ZoneId.systemDefault() }
    var chosen by remember {
        mutableStateOf(java.time.Instant.ofEpochMilli(initialPickup ?: (System.currentTimeMillis() + 3_600_000L))
            .atZone(zone).toLocalDateTime().withSecond(0).withNano(0))
    }
    var scheduleError by remember { mutableStateOf<String?>(null) }
    val resolved = runCatching { ScheduleTime.resolve(chosen.year, chosen.monthValue, chosen.dayOfMonth, chosen.hour, chosen.minute, zone.id) }
    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.schedule)) }, navigationIcon = { IconButton(onBack) { Icon(Icons.Default.ArrowBack, "Back") } }) }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("Choose pickup time", fontSize = 26.sp, fontWeight = FontWeight.Bold)
            Text("Choose a pickup 15 minutes to 30 days ahead. Times use your local zone: ${zone.id}. The label changes between PST/PDT automatically.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedButton(onClick = {
                android.app.DatePickerDialog(context, { _, year, month, day ->
                    chosen = chosen.with(java.time.LocalDate.of(year, month + 1, day)); scheduleError = null
                }, chosen.year, chosen.monthValue - 1, chosen.dayOfMonth).show()
            }, modifier = Modifier.fillMaxWidth()) { Text(chosen.toLocalDate().format(java.time.format.DateTimeFormatter.ofPattern("EEE, d MMM yyyy"))) }
            OutlinedButton(onClick = {
                android.app.TimePickerDialog(context, { _, hour, minute ->
                    chosen = chosen.withHour(hour).withMinute(minute); scheduleError = null
                }, chosen.hour, chosen.minute, android.text.format.DateFormat.is24HourFormat(context)).show()
            }, modifier = Modifier.fillMaxWidth()) { Text(chosen.toLocalTime().format(java.time.format.DateTimeFormatter.ofPattern("h:mm a"))) }
            resolved.getOrNull()?.let { Text(ScheduleTime.label(it, zone.id), fontWeight = FontWeight.SemiBold) }
            (scheduleError ?: resolved.exceptionOrNull()?.localizedMessage)?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Text("Development booking only. No real driver is reserved. Cancel from Upcoming; to change the time, cancel and book again.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            PrimaryButton("Use this pickup time", {
                val at = resolved.getOrNull()
                if (at == null || !ScheduleTime.isBookable(at, System.currentTimeMillis())) {
                    scheduleError = resolved.exceptionOrNull()?.localizedMessage ?: "Choose a pickup 15 minutes to 30 days from now."
                } else onChoose(at, zone.id)
            })
            OutlinedButton(onClick = { onChoose(null, null) }, modifier = Modifier.fillMaxWidth()) { Text("Switch to Ride Now") }
        }
    }
}

@Composable
private fun ConfirmationScreen(
    draft: BookingDraft,
    reviewedOption: RideOption?,
    serverRoute: RouteEstimate?,
    routeChangeReason: String?,
    busy: Boolean,
    errorMessage: String?,
    paymentMethod: PaymentMethod?,
    nearbyDriver: DriverAvailability?,
    nearbyDriverChecking: Boolean,
    onOpenPayment: () -> Unit,
    onBack: () -> Unit,
    onRequest: () -> Unit
) {
    val routeEstimate = serverRoute ?: remember(draft.routeEstimate, draft.pickup, draft.destination) { draft.routeEstimate ?: FareEstimator.route(draft.pickup, draft.destination) }
    val rideOptions = remember(routeEstimate) { FareEstimator.rideOptions(routeEstimate) }
    val option = reviewedOption ?: rideOptions.first { it.tier == draft.selectedTier }

    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.booking_summary)) }, navigationIcon = { IconButton(onBack, enabled = !busy) { Icon(Icons.Default.ArrowBack, "Back") } }) },
        bottomBar = {
            Surface(shadowElevation = 8.dp) {
                Column(Modifier.navigationBarsPadding().padding(16.dp)) {
                    errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp); Spacer(Modifier.height(8.dp)) }
                    PrimaryButton(
                        if (busy) "Please wait…" else if (reviewedOption == null) "Get current fare" else "Confirm $${"%.2f".format(option.fareCad)} CAD",
                        onRequest,
                        enabled = !busy && (reviewedOption == null || paymentMethod != null)
                    )
                }
            }
        }
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
            RouteLine(stringResource(R.string.pickup), draft.pickup.name, NovaSuccess)
            RouteLine(stringResource(R.string.destination), draft.destination?.name ?: "—", NovaBlue)
            routeEstimate?.let { route ->
                Spacer(Modifier.height(8.dp))
                Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                    Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.DirectionsCar, null, tint = NovaBlue)
                        Spacer(Modifier.width(10.dp))
                        Column {
                            Text("${"%.1f".format(route.distanceKm)} km · about ${route.durationMinutes} min", fontWeight = FontWeight.SemiBold)
                            Text(if (route.isApproximate) "Approximate route estimate" else "Selected Google road route", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp)
                        }
                    }
                }
            }
            routeChangeReason?.let { reason ->
                Spacer(Modifier.height(8.dp))
                Text(reason, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
            }
            Spacer(Modifier.height(20.dp))
            val livePickupEta = nearbyDriver?.takeIf { it.available }?.etaMinutes
            val pickupEtaLabel = when {
                draft.scheduled -> "${option.title} · Scheduled ride"
                livePickupEta != null -> "${option.title} · $livePickupEta min away"
                nearbyDriverChecking -> "${option.title} · Checking nearby drivers…"
                else -> "${option.title} · No nearby driver online"
            }
            Text(pickupEtaLabel, fontWeight = FontWeight.Bold, fontSize = 20.sp)
            Text(if (draft.scheduled) draft.scheduleLabel else stringResource(R.string.ride_now), color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(20.dp)); FareRows(option)
            Surface(
                modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).clickable(onClick = onOpenPayment),
                color = MaterialTheme.colorScheme.surfaceVariant
            ) {
                Row(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.CreditCard, null, tint = NovaBlue)
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        Text(stringResource(R.string.payment), color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                        Text(paymentMethod?.displayLabel ?: "Choose a payment method", fontWeight = FontWeight.SemiBold)
                    }
                    Icon(Icons.Default.ChevronRight, null)
                }
            }
            SummaryRow("Cancellation", if (draft.scheduled) "Free while scheduled" else "Free for 2 minutes")
            Spacer(Modifier.height(18.dp)); Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surfaceVariant) { Row(Modifier.padding(14.dp)) { Icon(Icons.Default.VerifiedUser, null, tint = NovaBlue); Spacer(Modifier.width(10.dp)); Text("Trip PIN and safety tools will be available when a driver is assigned.", fontSize = 13.sp) } }
            Spacer(Modifier.height(16.dp))
            Text(if (reviewedOption == null) "Get the current fare, then review it before confirming. Development payment references never create a real charge." else "Review the refreshed route, GST-inclusive fare and selected payment method. Nearby-driver ETA refreshes from the latest online driver location; payments remain development-only.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun RouteLine(label: String, value: String, color: Color) { Row(Modifier.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(12.dp).clip(CircleShape).background(color)); Spacer(Modifier.width(12.dp)); Column { Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp); Text(value, fontWeight = FontWeight.SemiBold) } } }
@Composable
private fun SummaryRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(label, Modifier.weight(0.42f), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, Modifier.weight(0.58f), fontWeight = FontWeight.Medium,
            textAlign = androidx.compose.ui.text.style.TextAlign.End)
    }
}

@Composable
private fun FareRows(option: RideOption) {
    option.breakdown?.let { fare ->
        SummaryRow("Subtotal", "$${"%.2f".format(fare.subtotalCents / 100.0)} CAD")
        SummaryRow("GST (included)", "$${"%.2f".format(fare.gstCents / 100.0)} CAD")
        SummaryRow("Total", "$${"%.2f".format(fare.totalCents / 100.0)} CAD")
    } ?: SummaryRow("Fare estimate", "$${"%.2f".format(option.fareCad)} CAD")
}

@Composable
private fun MatchingScreen(
    backendMode: Boolean,
    repository: RideNovaRepository,
    syncError: String?,
    trip: RideTrip?,
    onTripUpdate: (RideTrip) -> Unit,
    onOpenTrips: () -> Unit,
    onReturnHome: () -> Unit
) {
    if (trip == null) {
        Scaffold(
            topBar = { TopAppBar(title = { Text("Ride status") }) }
        ) { pad ->
            Column(
                Modifier.padding(pad).fillMaxSize().padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Icon(Icons.Default.DirectionsCar, null, tint = NovaBlue, modifier = Modifier.size(52.dp))
                Spacer(Modifier.height(14.dp))
                Text("No active ride", fontWeight = FontWeight.Bold, fontSize = 22.sp)
                Text("Your current and scheduled rides are available in Trips.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(18.dp))
                PrimaryButton("View Trips", onOpenTrips)
            }
        }
        return
    }

    var now by remember(trip.id) { mutableLongStateOf(System.currentTimeMillis()) }
    var showCancelDialog by remember(trip.id) { mutableStateOf(false) }
    val cancelScope = rememberCoroutineScope()
    var cancelBusy by remember { mutableStateOf(false) }
    var cancelError by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(trip.id, trip.status) {
        if (!backendMode && trip.status == TripStatus.SEARCHING) {
            delay(4_500)
            onTripUpdate(
                trip.copy(
                    status = TripStatus.DRIVER_ASSIGNED,
                    driver = TripPrototypeFactory.demoDriver,
                    pin = "5824",
                    updatedAtEpochMs = System.currentTimeMillis()
                )
            )
        }
    }

    LaunchedEffect(trip.id, trip.status) {
        while (trip.status in liveTripStatuses) {
            now = System.currentTimeMillis()
            delay(1_000)
        }
    }

    val graceSeconds = ((trip.graceEndsAtEpochMs - now + 999L) / 1000L).coerceAtLeast(0L)
    val cancellationFee = if (graceSeconds > 0) 0.0 else 5.0
    val cancellable = trip.status in setOf(TripStatus.SEARCHING, TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_ARRIVED)

    if (showCancelDialog) {
        AlertDialog(
            onDismissRequest = { showCancelDialog = false },
            icon = { Icon(Icons.Default.Cancel, null) },
            title = { Text("Cancel this ride?") },
            text = {
                Text(
                    if (backendMode) "The server applies the cancellation policy at confirmation. No real card is charged in this development build."
                    else if (cancellationFee == 0.0)
                        "You're still inside RideNova's 2-minute grace period. This prototype cancellation is free."
                    else
                        "The 2-minute grace period has ended. The current prototype cancellation fee is $5.00 CAD."
                )
            },
            dismissButton = {
                TextButton(onClick = { showCancelDialog = false }) { Text("Keep ride") }
            },
            confirmButton = {
                Button(
                    enabled = !cancelBusy,
                    onClick = {
                        if (backendMode) {
                            cancelScope.launch {
                                cancelBusy = true
                                runCatching { repository.cancelRide(trip.id) }
                                    .onSuccess { onTripUpdate(it); showCancelDialog = false; cancelError = null }
                                    .onFailure { cancelError = it.localizedMessage }
                                cancelBusy = false
                            }
                            return@Button
                        }
                        onTripUpdate(
                            trip.copy(
                                status = TripStatus.CANCELLED_BY_RIDER,
                                cancellationFeeCad = cancellationFee,
                                updatedAtEpochMs = System.currentTimeMillis()
                            )
                        )
                        showCancelDialog = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) { Text(if (cancelBusy) "Cancelling…" else cancelError ?: "Cancel ride") }
            }
        )
    }

    val mapContext = LocalContext.current
    val position = trip.driverPosition
    val freshPosition = position?.takeIf {
        it.recordedAtEpochMs <= now + 5_000 && now - it.recordedAtEpochMs <= 30_000
    }?.let { RoutePoint(it.latitude, it.longitude) }
    val pickupPoint = trip.draft.pickup.latitude?.let { lat ->
        trip.draft.pickup.longitude?.let { lng -> RoutePoint(lat, lng) }
    }
    val driverPoint = when {
        trip.status == TripStatus.DRIVER_ARRIVED -> freshPosition ?: pickupPoint // Prefer fresh Driver GPS; fall back to the pickup marker.
        trip.status in setOf(TripStatus.DRIVER_ASSIGNED, TripStatus.TRIP_STARTED) -> freshPosition
        else -> null
    }
    var roadRoute by remember(trip.id) { mutableStateOf<List<RoutePoint>>(emptyList()) }
    var approachRoute by remember(trip.id) { mutableStateOf<List<RoutePoint>>(emptyList()) }
    LaunchedEffect(trip.id, trip.draft.pickup, trip.draft.destination) {
        roadRoute = emptyList()
        if (trip.draft.routeEstimate?.path.orEmpty().size < 2 && googleMapsConfigured() && trip.draft.destination != null) {
            roadRoute = GoogleRoutesService.computeDrivingRoutes(mapContext, trip.draft.pickup, trip.draft.destination)
                .getOrNull()?.let { it.best ?: it.fastest }?.path.orEmpty()
        }
    }
    LaunchedEffect(trip.id, trip.status, driverPoint) {
        approachRoute = emptyList()
        if (trip.status == TripStatus.DRIVER_ASSIGNED && driverPoint != null && pickupPoint != null && googleMapsConfigured()) {
            val start = PlaceSuggestion("Reported test position", "", driverPoint.latitude, driverPoint.longitude)
            approachRoute = GoogleRoutesService.computeDrivingRoutes(mapContext, start, trip.draft.pickup)
                .getOrNull()?.let { it.best ?: it.fastest }?.path.orEmpty()
        }
    }
    val plannedRoute = trip.draft.routeEstimate?.path?.takeIf { it.size > 1 } ?: roadRoute

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (syncError != null) "Reconnecting…" else "Your ride") },
                navigationIcon = { IconButton(onClick = onOpenTrips) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { pad ->
        Column(
            Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState())
        ) {
            Box(Modifier.fillMaxWidth().height(265.dp)) {
                RideNovaMap(
                    modifier = Modifier.fillMaxSize(),
                    pickup = trip.draft.pickup,
                    destination = trip.draft.destination,
                    routePoints = plannedRoute,
                    driverPoint = driverPoint,
                    driverTitle = if (trip.status == TripStatus.DRIVER_ARRIVED) "Driver at pickup" else "RideNova driver · latest position",
                    approachPoints = approachRoute,
                    progressPoint = if (trip.status == TripStatus.TRIP_STARTED) driverPoint else null,
                    compact = true
                )
                Surface(
                    modifier = Modifier.align(Alignment.TopStart).padding(14.dp),
                    shape = RoundedCornerShape(18.dp),
                    color = MaterialTheme.colorScheme.surface.copy(alpha = .95f),
                    shadowElevation = 4.dp
                ) {
                    Text(
                        tripStatusLabel(trip.status),
                        modifier = Modifier.padding(horizontal = 13.dp, vertical = 8.dp),
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }

            if (trip.status in setOf(TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_ARRIVED, TripStatus.TRIP_STARTED)) {
                Text(
                    when {
                        trip.status == TripStatus.DRIVER_ARRIVED -> "Driver marked arrived · latest location remains visible on the map"
                        position == null -> "Driver location unavailable · map shows the planned route, not live progress"
                        freshPosition == null -> "Driver location is over 30 seconds old · waiting for a fresh update"
                        trip.status == TripStatus.TRIP_STARTED -> "Driver location update · route progress follows the latest reported position"
                        approachRoute.size > 1 -> "Live driver update · route leads toward your pickup"
                        else -> "Live driver update · refreshing the route toward pickup"
                    },
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 9.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp
                )
            }

            Column(Modifier.padding(20.dp)) {
                Text(
                    when (trip.status) {
                        TripStatus.SEARCHING -> "Finding your driver"
                        TripStatus.DRIVER_ASSIGNED -> "Your driver is on the way"
                        TripStatus.DRIVER_ARRIVED -> "Your driver has arrived"
                        TripStatus.TRIP_STARTED -> "You're on your way"
                        TripStatus.COMPLETED -> "Ride completed"
                        TripStatus.CANCELLED_BY_RIDER -> "Ride cancelled"
                        TripStatus.SCHEDULED -> "Ride scheduled"
                        TripStatus.SCHEDULE_EXPIRED -> "Scheduled pickup missed"
                    },
                    fontSize = 26.sp,
                    fontWeight = FontWeight.Black,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    "${trip.draft.pickup.name}  →  ${trip.draft.destination?.name ?: "Destination"}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(16.dp))

                if (trip.status == TripStatus.TRIP_STARTED && trip.liveTrip != null) {
                    val live = trip.liveTrip
                    Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("Live trip progress", fontWeight = FontWeight.Bold)
                                Text("~${live.remainingEtaMinutes} min", fontWeight = FontWeight.Bold)
                            }
                            LinearProgressIndicator(
                                progress = { live.progress.toFloat().coerceIn(0f, 1f) },
                                modifier = Modifier.fillMaxWidth().height(7.dp).clip(CircleShape)
                            )
                            Text("${"%.1f".format(live.remainingDistanceKm)} km remaining · updated from Driver GPS",
                                color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                        }
                    }
                    Spacer(Modifier.height(14.dp))
                }

                if (trip.status == TripStatus.SEARCHING) {
                    Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                        Row(
                            Modifier.fillMaxWidth().padding(18.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            CircularProgressIndicator(Modifier.size(34.dp), strokeWidth = 3.dp)
                            Spacer(Modifier.width(14.dp))
                            Column {
                                Text(if (backendMode) "Matching with an online RideNova driver" else "Contacting nearby drivers", fontWeight = FontWeight.Bold)
                                Text(if (backendMode) "Looking for an available driver near your pickup. You can keep this screen open to follow updates." else "RideNova is matching your selected ${trip.option.title} ride.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                            }
                        }
                    }
                }

                trip.driver?.let { driver ->
                    if (trip.status in setOf(TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_ARRIVED, TripStatus.TRIP_STARTED)) {
                        DriverCard(driver = driver, pin = trip.pin, arrived = trip.status != TripStatus.DRIVER_ASSIGNED)
                        Spacer(Modifier.height(14.dp))
                    }
                }

                Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                    Column(Modifier.fillMaxWidth().padding(16.dp)) {
                        SummaryRow("Ride", trip.option.title)
                        FareRows(trip.option)
                        trip.payment?.let { SummaryRow("Payment", "${it.methodLabel} · ${paymentStatusLabel(it.status)}") }
                        trip.draft.routeEstimate?.let {
                            SummaryRow("Route", "${"%.1f".format(it.distanceKm)} km · ${it.durationMinutes} min")
                        }
                        SummaryRow("Trip ID", trip.id)
                    }
                }

                if (cancellable) {
                    Spacer(Modifier.height(14.dp))
                    Surface(shape = RoundedCornerShape(18.dp), color = if (graceSeconds > 0) NovaSuccess.copy(alpha = .09f) else MaterialTheme.colorScheme.surfaceVariant) {
                        Row(
                            Modifier.fillMaxWidth().padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Timer, null, tint = if (graceSeconds > 0) NovaSuccess else MaterialTheme.colorScheme.onSurfaceVariant)
                            Spacer(Modifier.width(10.dp))
                            Column {
                                Text(
                                    if (graceSeconds > 0)
                                        "Free cancellation · ${graceSeconds / 60}:${(graceSeconds % 60).toString().padStart(2, '0')} remaining"
                                    else
                                        if (backendMode) "$${"%.2f".format(trip.cancellationFeeAfterGraceCad)} development cancellation fee" else "$5.00 cancellation fee now applies",
                                    fontWeight = FontWeight.SemiBold
                                )
                                Text(if (backendMode) "Server time and policy determine the final fee; no actual charge is made." else "Prototype policy: 2-minute grace period after requesting.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp)
                            }
                        }
                    }
                    Spacer(Modifier.height(10.dp))
                    OutlinedButton(
                        onClick = { showCancelDialog = true },
                        modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
                        shape = RoundedCornerShape(16.dp)
                    ) { Text("Cancel ride") }
                }

                when (trip.status) {
                    TripStatus.DRIVER_ASSIGNED -> {
                        Spacer(Modifier.height(12.dp))
                        if (!backendMode) PrototypeAction("Demo: driver has arrived") {
                            onTripUpdate(trip.copy(status = TripStatus.DRIVER_ARRIVED, updatedAtEpochMs = System.currentTimeMillis()))
                        }
                    }
                    TripStatus.DRIVER_ARRIVED -> {
                        Spacer(Modifier.height(12.dp))
                        if (!backendMode) PrototypeAction("Demo: start trip") {
                            onTripUpdate(trip.copy(status = TripStatus.TRIP_STARTED, updatedAtEpochMs = System.currentTimeMillis()))
                        }
                    }
                    TripStatus.TRIP_STARTED -> {
                        Spacer(Modifier.height(12.dp))
                        if (!backendMode) PrototypeAction("Demo: complete trip") {
                            onTripUpdate(trip.copy(
                                status = TripStatus.COMPLETED,
                                updatedAtEpochMs = System.currentTimeMillis(),
                                payment = trip.payment?.copy(
                                    status = PaymentStatus.CAPTURED_DEMO,
                                    amountCents = trip.option.breakdown?.totalCents ?: (trip.option.fareCad * 100).toLong()
                                )
                            ))
                        }
                    }
                    TripStatus.COMPLETED, TripStatus.SCHEDULE_EXPIRED -> {
                        Spacer(Modifier.height(18.dp))
                        PrimaryButton("Done", onReturnHome)
                        Spacer(Modifier.height(8.dp))
                        OutlinedButton(onOpenTrips, Modifier.fillMaxWidth()) { Text("View trip history") }
                    }
                    TripStatus.CANCELLED_BY_RIDER -> {
                        Spacer(Modifier.height(18.dp))
                        if (trip.cancellationFeeCad > 0) {
                            Text("Prototype cancellation fee: $${"%.2f".format(trip.cancellationFeeCad)} CAD", color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Spacer(Modifier.height(8.dp))
                        }
                        PrimaryButton("Return home", onReturnHome)
                    }
                    TripStatus.SCHEDULED -> {
                        Spacer(Modifier.height(16.dp))
                        Text("Scheduled for ${trip.draft.scheduleLabel}", fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.height(12.dp))
                        PrimaryButton("View Trips", onOpenTrips)
                    }
                    TripStatus.SEARCHING -> Unit
                }

                if (trip.status !in setOf(TripStatus.COMPLETED, TripStatus.CANCELLED_BY_RIDER, TripStatus.SCHEDULE_EXPIRED)) {
                    Spacer(Modifier.height(18.dp))
                    Text(
                        if (backendMode) "Development ride · live driver updates · payments are simulated." else "Offline prototype: driver progress is simulated locally. No real driver is contacted or payment collected.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                }
            }
        }
    }
}

@Composable
private fun DriverCard(driver: DriverProfile, pin: String?, arrived: Boolean) {
    Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface, shadowElevation = 2.dp) {
        Column(Modifier.fillMaxWidth().padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.size(58.dp).clip(CircleShape).background(NovaBlue.copy(alpha = .10f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(Icons.Default.Person, null, tint = NovaBlue, modifier = Modifier.size(30.dp))
                }
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    Text(driver.name, fontWeight = FontWeight.Bold, fontSize = 19.sp)
                    Text("★ ${"%.2f".format(driver.rating)} · ${driver.vehicle}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("${driver.colour} · ${driver.plate}", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                }
                Surface(shape = RoundedCornerShape(14.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                    Text(
                        if (arrived) "Arrived" else "${driver.pickupEtaMinutes} min",
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 7.dp),
                        fontWeight = FontWeight.Bold
                    )
                }
            }
            pin?.let {
                Spacer(Modifier.height(14.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                Spacer(Modifier.height(12.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Lock, null, tint = NovaBlue)
                    Spacer(Modifier.width(10.dp))
                    Column {
                        Text("Ride PIN", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                        Text(it, fontWeight = FontWeight.Black, fontSize = 22.sp, letterSpacing = 4.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun PrototypeAction(label: String, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
        shape = RoundedCornerShape(16.dp),
        colors = ButtonDefaults.buttonColors(containerColor = NovaBlue)
    ) {
        Icon(Icons.Default.PlayArrow, null)
        Spacer(Modifier.width(8.dp))
        Text(label, fontWeight = FontWeight.Bold)
    }
}

private val liveTripStatuses = setOf(TripStatus.SEARCHING, TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_ARRIVED, TripStatus.TRIP_STARTED)
private val pastTripStatuses = setOf(TripStatus.COMPLETED, TripStatus.CANCELLED_BY_RIDER, TripStatus.SCHEDULE_EXPIRED)

private fun tripStatusLabel(status: TripStatus): String = when (status) {
    TripStatus.SCHEDULED -> "Scheduled"
    TripStatus.SEARCHING -> "Searching"
    TripStatus.DRIVER_ASSIGNED -> "Driver assigned"
    TripStatus.DRIVER_ARRIVED -> "Driver arrived"
    TripStatus.TRIP_STARTED -> "In progress"
    TripStatus.COMPLETED -> "Completed"
    TripStatus.CANCELLED_BY_RIDER -> "Cancelled"
    TripStatus.SCHEDULE_EXPIRED -> "Pickup missed · no charge"
}

private fun tripEventLabel(status: TripStatus): String = when (status) {
    TripStatus.COMPLETED -> "Completed"
    TripStatus.CANCELLED_BY_RIDER -> "Cancelled"
    TripStatus.SCHEDULE_EXPIRED -> "Pickup missed"
    else -> "Last updated"
}

private fun tripDateTime(epochMillis: Long): String =
    DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(Date(epochMillis))

@Composable
private fun TripsScreen(
    nav: NavHostController,
    trips: List<RideTrip>,
    backendMode: Boolean,
    repository: RideNovaRepository,
    syncError: String?,
    onTripUpdate: (RideTrip) -> Unit,
    onOpenTrip: (String) -> Unit,
    onStartScheduled: (String) -> Unit
) {
    val active = trips.filter { it.status in setOf(TripStatus.SEARCHING, TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_ARRIVED, TripStatus.TRIP_STARTED) }
    val scheduled = trips.filter { it.status == TripStatus.SCHEDULED }.sortedBy { it.draft.scheduledAtEpochMs ?: Long.MAX_VALUE }
    val recent = trips.filter { it.status in setOf(TripStatus.COMPLETED, TripStatus.CANCELLED_BY_RIDER, TripStatus.SCHEDULE_EXPIRED) }
        .sortedByDescending { it.updatedAtEpochMs }
    var cancelTarget by remember { mutableStateOf<RideTrip?>(null) }
    var cancelBusy by remember { mutableStateOf(false) }
    var cancelError by remember { mutableStateOf<String?>(null) }
    val cancelScope = rememberCoroutineScope()
    cancelTarget?.let { target ->
        AlertDialog(onDismissRequest = { if (!cancelBusy) cancelTarget = null },
            title = { Text("Cancel scheduled ride?") },
            text = { Text(cancelError ?: "Cancellation is free while scheduled. Once matching starts, the ride's cancellation policy applies. No actual payment is collected in this development build.") },
            confirmButton = { TextButton(enabled = !cancelBusy, onClick = {
                cancelScope.launch {
                    cancelBusy = true
                    runCatching { repository.cancelRide(target.id) }
                        .onSuccess { onTripUpdate(it); cancelTarget = null }
                        .onFailure { cancelError = it.localizedMessage ?: "Could not cancel; try again." }
                    cancelBusy = false
                }
            }) { Text(if (cancelBusy) "Cancelling…" else "Cancel ride") } },
            dismissButton = { TextButton(enabled = !cancelBusy, onClick = { cancelTarget = null }) { Text("Keep ride") } })
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.trips)) }) },
        bottomBar = { BottomBar(nav = nav, selectedRoute = Routes.TRIPS) }
    ) { pad ->
        Column(
            Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Text("Your rides", fontSize = 27.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
            Text("Active, scheduled and recent RideNova trips stay together here.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            syncError?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            if (active.isNotEmpty()) {
                Text("Current ride", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                active.forEach { trip ->
                    TripCard(trip = trip, onClick = { onOpenTrip(trip.id) })
                }
            }

            Text("Upcoming", fontWeight = FontWeight.Bold, fontSize = 18.sp)
            if (scheduled.isEmpty()) {
                EmptyTripCard("No scheduled rides", "Schedule a future pickup from the ride-selection screen.")
            } else {
                scheduled.forEach { trip ->
                    TripCard(
                        trip = trip,
                        onClick = { onOpenTrip(trip.id) },
                        footer = {
                            Text(if (backendMode) "Matching starts at pickup time while the development server is running. No real driver is reserved." else "Offline prototype: matching starts manually using the demo button.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            OutlinedButton(onClick = { cancelTarget = trip; cancelError = null }, modifier = Modifier.fillMaxWidth()) { Text("Cancel scheduled ride") }
                            if (!backendMode) OutlinedButton(
                                onClick = { onStartScheduled(trip.id) },
                                modifier = Modifier.fillMaxWidth()
                            ) { Text("Demo: start matching") }
                        }
                    )
                }
            }

            Text("Recent", fontWeight = FontWeight.Bold, fontSize = 18.sp)
            if (recent.isEmpty()) {
                EmptyTripCard("No past rides yet", "Your completed and cancelled rides will appear here.")
                OutlinedButton(onClick = { navigateTopLevel(nav, Routes.HOME) }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Find a ride") }
            } else {
                recent.forEach { trip -> TripCard(trip = trip, onClick = { onOpenTrip(trip.id) }) }
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun TripCard(
    trip: RideTrip,
    onClick: () -> Unit,
    footer: (@Composable () -> Unit)? = null
) {
    Surface(
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).clickable(onClick = onClick),
        shape = RoundedCornerShape(22.dp),
        color = MaterialTheme.colorScheme.surfaceVariant
    ) {
        Column(Modifier.fillMaxWidth().padding(17.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(46.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surface), contentAlignment = Alignment.Center) {
                    Icon(
                        when (trip.status) {
                            TripStatus.COMPLETED -> Icons.Default.CheckCircle
                            TripStatus.CANCELLED_BY_RIDER -> Icons.Default.Cancel
                            TripStatus.SCHEDULE_EXPIRED -> Icons.Default.EventBusy
                            TripStatus.SCHEDULED -> Icons.Default.Event
                            else -> Icons.Default.DirectionsCar
                        },
                        null,
                        tint = when (trip.status) {
                            TripStatus.COMPLETED -> NovaSuccess
                            TripStatus.CANCELLED_BY_RIDER -> MaterialTheme.colorScheme.error
                            TripStatus.SCHEDULE_EXPIRED -> MaterialTheme.colorScheme.onSurfaceVariant
                            else -> NovaBlue
                        }
                    )
                }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(trip.draft.destination?.name ?: "Destination", fontWeight = FontWeight.Bold)
                    Text(
                        if (trip.status == TripStatus.SCHEDULED) trip.draft.scheduleLabel else tripStatusLabel(trip.status),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 13.sp
                    )
                    Text(
                        if (trip.status == TripStatus.SCHEDULED) "Booked ${tripDateTime(trip.requestedAtEpochMs)}"
                        else if (trip.status in setOf(TripStatus.COMPLETED, TripStatus.CANCELLED_BY_RIDER, TripStatus.SCHEDULE_EXPIRED))
                            "${tripEventLabel(trip.status)} ${tripDateTime(trip.updatedAtEpochMs)}"
                        else "Requested ${tripDateTime(trip.requestedAtEpochMs)}",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                }
                Text("$${"%.2f".format(trip.option.fareCad)}", fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                trip.draft.routeEstimate?.let {
                    AssistChip(onClick = {}, label = { Text("${"%.1f".format(it.distanceKm)} km") })
                    AssistChip(onClick = {}, label = { Text("${it.durationMinutes} min") })
                }
            }
            if (trip.status == TripStatus.CANCELLED_BY_RIDER && trip.cancellationFeeCad > 0) {
                Text("Cancellation fee: $${"%.2f".format(trip.cancellationFeeCad)} CAD", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
            }
            footer?.let {
                Spacer(Modifier.height(10.dp))
                it()
            }
        }
    }
}

@Composable
private fun EmptyTripCard(title: String, subtitle: String) {
    Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
        Row(Modifier.fillMaxWidth().padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(46.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surface), contentAlignment = Alignment.Center) {
                Icon(Icons.Default.Event, null, tint = NovaBlue)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.Bold)
                Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
            }
        }
    }
}

@Composable
private fun TripDetailScreen(
    trip: RideTrip?,
    repository: RideNovaRepository,
    onAuthorizeTest: suspend (String) -> String,
    onBack: () -> Unit,
    onOpenLiveRide: () -> Unit,
    onRideAgain: (RideTrip) -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Trip details") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { pad ->
        if (trip == null) {
            Column(
                Modifier.padding(pad).fillMaxSize().padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Icon(Icons.Default.ReceiptLong, null, tint = NovaBlue, modifier = Modifier.size(48.dp))
                Spacer(Modifier.height(12.dp))
                Text("Trip unavailable", fontSize = 22.sp, fontWeight = FontWeight.SemiBold)
                Text("This trip could not be loaded.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                TextButton(onClick = onBack) { Text("Back to trips") }
            }
            return@Scaffold
        }

        val isLive = trip.status in setOf(TripStatus.SEARCHING, TripStatus.DRIVER_ASSIGNED, TripStatus.DRIVER_ARRIVED, TripStatus.TRIP_STARTED)
        val context = LocalContext.current
        val archivedRoute = trip.draft.routeEstimate?.path.orEmpty()
        val pickup = trip.draft.pickup
        val destination = trip.draft.destination
        val pickupPoint = pickup.latitude?.let { lat -> pickup.longitude?.let { lng -> RoutePoint(lat, lng) } }
        val destinationPoint = destination?.latitude?.let { lat -> destination.longitude?.let { lng -> RoutePoint(lat, lng) } }
        var currentRoadPreview by remember(trip.id) { mutableStateOf<List<RoutePoint>>(emptyList()) }
        var loadingRoadPreview by remember(trip.id) { mutableStateOf(false) }
        LaunchedEffect(trip.id, archivedRoute) {
            currentRoadPreview = emptyList()
            loadingRoadPreview = false
            // Older backend rides retain coordinates but not road geometry. Never describe a
            // freshly calculated road route as the GPS track actually driven by the rider.
            if (archivedRoute.size < 2 && googleMapsConfigured() && pickupPoint != null && destinationPoint != null) {
                loadingRoadPreview = true
                currentRoadPreview = GoogleRoutesService.computeDrivingRoutes(
                    context, pickup, destination
                ).getOrNull()?.let { it.best ?: it.fastest }?.path?.takeIf { it.size > 1 }.orEmpty()
                loadingRoadPreview = false
            }
        }
        val mapRoute = when {
            archivedRoute.size > 1 -> archivedRoute
            currentRoadPreview.size > 1 -> currentRoadPreview
            pickupPoint != null && destinationPoint != null -> listOf(pickupPoint, destinationPoint)
            else -> emptyList()
        }

        Column(
            Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState())
        ) {
            Box(Modifier.fillMaxWidth().height(235.dp)) {
                RideNovaMap(
                    modifier = Modifier.fillMaxSize(),
                    pickup = trip.draft.pickup,
                    destination = trip.draft.destination,
                    routePoints = mapRoute,
                    compact = true
                )
                Surface(
                    modifier = Modifier.align(Alignment.TopStart).padding(14.dp),
                    shape = RoundedCornerShape(16.dp),
                    color = MaterialTheme.colorScheme.surface.copy(alpha = .95f),
                    shadowElevation = 4.dp
                ) {
                    Text(
                        tripStatusLabel(trip.status),
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }

            Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text(
                    when {
                        archivedRoute.size > 1 -> "Booking route preview · not a recorded GPS track"
                        currentRoadPreview.size > 1 -> "Current road route preview · not the route driven on this trip"
                        loadingRoadPreview -> "Finding a road route preview…"
                        mapRoute.size > 1 -> "Approximate straight-line connection · road route unavailable"
                        else -> "Trip route unavailable · pickup and destination coordinates are missing"
                    },
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp
                )
                Column {
                    Text(
                        trip.draft.destination?.name ?: "RideNova trip",
                        fontSize = 27.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        "${if (trip.draft.scheduled) "Booked" else "Requested"} ${tripDateTime(trip.requestedAtEpochMs)}",
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                    Column(Modifier.fillMaxWidth().padding(17.dp)) {
                        RouteLine("Pickup", trip.draft.pickup.address, NovaSuccess)
                        RouteLine("Destination", trip.draft.destination?.address ?: "Destination", NovaBlue)
                    }
                }

                Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                    Column(Modifier.fillMaxWidth().padding(17.dp)) {
                        SummaryRow("Ride", trip.option.title)
                        SummaryRow("Status", tripStatusLabel(trip.status))
                        if (trip.status in setOf(TripStatus.COMPLETED, TripStatus.CANCELLED_BY_RIDER, TripStatus.SCHEDULE_EXPIRED)) {
                            Text("${tripEventLabel(trip.status)} at", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                            Text(tripDateTime(trip.updatedAtEpochMs), fontWeight = FontWeight.SemiBold)
                        }
                        FareRows(trip.option)
                        trip.payment?.let { payment ->
                            SummaryRow("Payment method", payment.methodLabel)
                            SummaryRow("Payment status", paymentStatusLabel(payment.status))
                        }
                        if (trip.draft.scheduled) {
                            Text("Scheduled pickup", color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(trip.draft.scheduleLabel, fontWeight = FontWeight.SemiBold)
                        }
                        if (trip.status == TripStatus.SCHEDULE_EXPIRED) Text("The development server could not start this pickup within 15 minutes. No fee was recorded. Book a new ride when ready.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        trip.draft.routeEstimate?.let {
                            SummaryRow("Distance", "${"%.1f".format(it.distanceKm)} km")
                            SummaryRow("Estimated time", "${it.durationMinutes} min")
                        }
                        if (trip.status == TripStatus.CANCELLED_BY_RIDER) {
                            SummaryRow("Cancellation fee", "$${"%.2f".format(trip.cancellationFeeCad)} CAD")
                        }
                    }
                }

                trip.driver?.let { driver ->
                    Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                        Row(Modifier.fillMaxWidth().padding(17.dp), verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                Modifier.size(48.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surface),
                                contentAlignment = Alignment.Center
                            ) { Icon(Icons.Default.Person, null, tint = NovaBlue) }
                            Spacer(Modifier.width(12.dp))
                            Column(Modifier.weight(1f)) {
                                Text(driver.name, fontWeight = FontWeight.SemiBold)
                                Text("★ ${"%.2f".format(driver.rating)} · ${driver.colour} ${driver.vehicle}", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                                Text(driver.plate, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                            }
                        }
                    }
                }

                if (trip.status == TripStatus.COMPLETED) {
                    PassengerExperienceCard(trip.id, repository)
                    if (BuildConfig.RIDENOVA_ENVIRONMENT == "staging") {
                        var paymentFeedback by remember(trip.id) { mutableStateOf<String?>(null) }
                        var paymentBusy by remember(trip.id) { mutableStateOf(false) }
                        val scope = rememberCoroutineScope()
                        Button(onClick = {
                            paymentBusy = true
                            scope.launch {
                                paymentFeedback = runCatching { "Stripe test authorization: " + onAuthorizeTest(trip.id) }
                                    .getOrElse { it.localizedMessage ?: "Test authorization failed" }
                                paymentBusy = false
                            }
                        }, enabled = !paymentBusy) { Text("Authorize test payment") }
                        paymentFeedback?.let { Text(it, fontSize = 12.sp) }
                        Text("Test mode only. Ask an Owner to capture or refund it in Finance. No real money moves.", fontSize = 11.sp)
                    }
                }

                if (isLive) {
                    PrimaryButton("Open live ride", onOpenLiveRide)
                } else if (trip.status in setOf(TripStatus.COMPLETED, TripStatus.CANCELLED_BY_RIDER, TripStatus.SCHEDULE_EXPIRED)) {
                    PrimaryButton("Ride again", { onRideAgain(trip) })
                    Text(
                        "Uses this destination and ride category. Your current GPS location becomes the new pickup.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                }

                Text(
                    "Trip ID ${trip.id}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp
                )
                Spacer(Modifier.height(12.dp))
            }
        }
    }
}

@Composable
private fun PassengerExperienceCard(tripId: String, repository: RideNovaRepository) {
    val scope = rememberCoroutineScope()
    var experience by remember(tripId) { mutableStateOf<com.ridenova.passenger.data.RideExperience?>(null) }
    var loading by remember(tripId) { mutableStateOf(true) }
    var error by remember(tripId) { mutableStateOf<String?>(null) }
    var ratingOpen by remember { mutableStateOf(false) }
    var supportOpen by remember { mutableStateOf(false) }
    LaunchedEffect(tripId) {
        runCatching { repository.rideExperience(tripId) }
            .onSuccess { experience = it }
            .onFailure { error = it.localizedMessage ?: "Could not load trip feedback" }
        loading = false
    }
    Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
        Column(Modifier.fillMaxWidth().padding(17.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Star, null, tint = Color(0xFFFFB000))
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text("Your trip experience", fontWeight = FontWeight.Bold)
                    Text(when {
                        loading -> "Loading feedback…"
                        experience?.rating != null -> "Rated ${experience?.rating?.stars} out of 5"
                        else -> "Help recognize great service"
                    }, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { ratingOpen = true }, enabled = !loading, modifier = Modifier.weight(1f)) {
                    Text(if (experience?.rating == null) "Rate ride" else "Edit rating")
                }
                OutlinedButton(onClick = { supportOpen = true }, modifier = Modifier.weight(1f)) { Text("Get help") }
            }
            val cases = experience?.supportCaseCount ?: 0
            if (cases > 0) Text("$cases support ${if (cases == 1) "case" else "cases"} linked to this trip", fontSize = 12.sp)
        }
    }
    if (ratingOpen) PassengerRatingDialog(experience?.rating?.stars ?: 5, experience?.rating?.comment.orEmpty(),
        onDismiss = { ratingOpen = false }, onSubmit = { stars, tags, comment ->
            scope.launch {
                loading = true; error = null
                runCatching { repository.rateRide(tripId, stars, tags, comment) }
                    .onSuccess { experience = it; ratingOpen = false }
                    .onFailure { error = it.localizedMessage ?: "Could not save rating" }
                loading = false
            }
        })
    if (supportOpen) PassengerSupportDialog(onDismiss = { supportOpen = false }, onSubmit = { category, description ->
        scope.launch {
            loading = true; error = null
            runCatching { repository.createSupportCase(tripId, category, description) }
                .onSuccess {
                    supportOpen = false
                    experience = repository.rideExperience(tripId)
                }.onFailure { error = it.localizedMessage ?: "Could not create support case" }
            loading = false
        }
    })
}

@Composable
private fun PassengerRatingDialog(initialStars: Int, initialComment: String, onDismiss: () -> Unit,
                                  onSubmit: (Int, List<String>, String) -> Unit) {
    var stars by remember { mutableStateOf(initialStars) }
    var comment by remember { mutableStateOf(initialComment) }
    var selected by remember { mutableStateOf(setOf<String>()) }
    val tags = listOf("SAFE_DRIVING" to "Safe driving", "FRIENDLY" to "Friendly", "CLEAN_VEHICLE" to "Clean vehicle", "ON_TIME" to "On time")
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Rate your driver") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()).imePadding(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
                (1..5).forEach { value -> IconButton(onClick = { stars = value }) {
                    Icon(if (value <= stars) Icons.Default.Star else Icons.Default.StarBorder, "$value stars", tint = Color(0xFFFFB000))
                } }
            }
            Text("What stood out?", fontWeight = FontWeight.SemiBold)
            tags.forEach { (key, label) -> FilterChip(selected = key in selected, onClick = {
                selected = if (key in selected) selected - key else selected + key
            }, label = { Text(label) }, leadingIcon = if (key in selected) {{ Icon(Icons.Default.Check, null) }} else null) }
            OutlinedTextField(comment, { comment = it.take(500) }, Modifier.fillMaxWidth(), label = { Text("Comment (optional)") }, minLines = 3)
        }
    }, confirmButton = { Button(onClick = { onSubmit(stars, selected.toList(), comment) }) { Text("Save rating") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

@Composable
private fun PassengerSupportDialog(onDismiss: () -> Unit, onSubmit: (String, String) -> Unit) {
    var category by remember { mutableStateOf("LOST_ITEM") }
    var description by remember { mutableStateOf("") }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Trip support") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()).imePadding(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Choose the closest issue", color = MaterialTheme.colorScheme.onSurfaceVariant)
            listOf("LOST_ITEM" to "Lost item", "FARE" to "Fare or receipt", "SAFETY" to "Safety", "DRIVER" to "Driver concern", "APP" to "App issue").forEach { (key, label) ->
                FilterChip(selected = category == key, onClick = { category = key }, label = { Text(label) })
            }
            OutlinedTextField(description, { description = it.take(1000) }, Modifier.fillMaxWidth(), label = { Text("Tell us what happened") }, minLines = 4,
                supportingText = { Text("${description.trim().length}/1000 · at least 10 characters") })
        }
    }, confirmButton = { Button(enabled = description.trim().length >= 10, onClick = { onSubmit(category, description.trim()) }) { Text("Submit case") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

@Composable
private fun AccountScreen(nav: NavHostController, themeMode: RideNovaThemeMode, riderProfile: RiderProfile?, backendConfigured: Boolean, onEditProfile: () -> Unit, onLogout: () -> Unit) {
    var showLogout by remember { mutableStateOf(false) }
    if (showLogout) AlertDialog(
        onDismissRequest = { showLogout = false }, title = { Text("Sign out of RideNova?") },
        text = { Text("You’ll need to verify your phone number to access account rides again. Your server account and trip history will remain available.") },
        confirmButton = { TextButton(onClick = { showLogout = false; onLogout() }) { Text("Sign out") } },
        dismissButton = { TextButton(onClick = { showLogout = false }) { Text("Stay signed in") } })
    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.account)) }) },
        bottomBar = { BottomBar(nav = nav, selectedRoute = Routes.ACCOUNT) }
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(68.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
                    Icon(Icons.Default.Person, null, modifier = Modifier.size(34.dp))
                }
                Spacer(Modifier.width(14.dp))
                Column {
                    Text(riderProfile?.displayName?.takeIf { it.isNotBlank() } ?: "RideNova Rider", fontWeight = FontWeight.Bold, fontSize = 21.sp)
                    Text(riderProfile?.email?.takeIf { it.isNotBlank() } ?: riderProfile?.phone?.takeIf { it.isNotBlank() } ?: "Passenger profile", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Spacer(Modifier.height(26.dp))
            AccountMenuRow(Icons.Default.ManageAccounts, "Profile", "Name, verified phone and email") { onEditProfile() }
            AccountMenuRow(Icons.Default.CreditCard, stringResource(R.string.payment), "Cards & digital wallets") { nav.navigate(Routes.PAYMENT) }
            AccountMenuRow(Icons.Default.Place, stringResource(R.string.saved_places), "Home, work and favourites") { nav.navigate(Routes.SAVED_PLACES) }
            AccountMenuRow(Icons.Default.Security, stringResource(R.string.safety), "PIN, sharing and support") { nav.navigate(Routes.SAFETY) }
            AccountMenuRow(Icons.Default.Language, stringResource(R.string.language), "English · Français · Español") { nav.navigate(Routes.LANGUAGE) }
            AccountMenuRow(
                Icons.Default.DarkMode,
                "Appearance",
                when (themeMode) {
                    RideNovaThemeMode.SYSTEM -> "Use device setting"
                    RideNovaThemeMode.LIGHT -> "Light theme"
                    RideNovaThemeMode.DARK -> "Dark theme"
                }
            ) { nav.navigate(Routes.APPEARANCE) }
            AccountMenuRow(Icons.Default.Help, stringResource(R.string.help), "Support and legal") { nav.navigate(Routes.HELP) }
            Spacer(Modifier.height(18.dp))
            Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                Row(Modifier.fillMaxWidth().padding(13.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(if (backendConfigured) Icons.Default.CloudDone else Icons.Default.CloudOff, null, tint = if (backendConfigured) NovaSuccess else MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.width(10.dp))
                    Column {
                        Text(if (backendConfigured) "RideNova server connected" else "Development mode", fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
                        Text(if (backendConfigured) "Authenticated passenger account · tokens refresh securely" else "Local ride engine · offline prototype profile", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
                    }
                }
            }
            Spacer(Modifier.height(14.dp))
            OutlinedButton(onClick = { showLogout = true }, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) {
                Icon(Icons.Default.Logout, null); Spacer(Modifier.width(8.dp)); Text("Sign out")
            }
            Spacer(Modifier.height(18.dp))
        }
    }
}

@Composable
private fun AccountMenuRow(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit
) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).clickable(onClick = onClick).padding(vertical = 13.dp, horizontal = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, null, tint = NovaBlue)
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.SemiBold)
            Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
        }
        Icon(Icons.Default.ChevronRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun SavedPlacesScreen(
    home: PlaceSuggestion?,
    work: PlaceSuggestion?,
    syncing: Boolean,
    errorMessage: String?,
    onBack: () -> Unit,
    onEdit: (String) -> Unit,
    onClear: (String) -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Saved places") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().padding(20.dp)) {
            Text("Your everyday places", fontSize = 25.sp, fontWeight = FontWeight.Bold)
            Text("Save Home and Work once, then start a ride from the Home screen with one tap. Signed-in places sync with your RideNova account.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (syncing) { Spacer(Modifier.height(10.dp)); LinearProgressIndicator(Modifier.fillMaxWidth()) }
            errorMessage?.let { Spacer(Modifier.height(10.dp)); Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp) }
            Spacer(Modifier.height(18.dp))
            SavedPlaceCard("home", "Home", Icons.Default.Home, home, onEdit, onClear)
            Spacer(Modifier.height(12.dp))
            SavedPlaceCard("work", "Work", Icons.Default.Work, work, onEdit, onClear)
            Spacer(Modifier.height(18.dp))
            Surface(shape = RoundedCornerShape(18.dp), color = NovaBlue.copy(alpha = .10f)) {
                Row(Modifier.fillMaxWidth().padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Lock, null, tint = NovaBlue)
                    Spacer(Modifier.width(10.dp))
                    Text("Home, Work and recent destinations are stored by the development backend and return when you sign in again.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

private fun paymentStatusLabel(status: PaymentStatus): String = when (status) {
    PaymentStatus.NOT_CHARGED -> "Not charged"
    PaymentStatus.AUTHORIZED_DEMO -> "Development authorization"
    PaymentStatus.CAPTURED_DEMO -> "Development payment recorded"
    PaymentStatus.VOIDED -> "No charge"
}

@Composable
private fun PaymentMethodsScreen(
    methods: List<PaymentMethod>,
    busy: Boolean,
    errorMessage: String?,
    backendMode: Boolean,
    staging: Boolean,
    pendingTestSetup: Boolean,
    onStartTestSetup: () -> Unit,
    onVerifyTestSetup: () -> Unit,
    onBack: () -> Unit,
    onReturnToBooking: () -> Unit,
    fromBooking: Boolean,
    onAddDevelopmentCard: (String, String, Int, Int) -> Unit,
    onMakeDefault: (String) -> Unit,
    onRemove: (String) -> Unit
) {
    var showAdd by remember { mutableStateOf(false) }
    var brand by remember { mutableStateOf("Visa") }
    var last4 by remember { mutableStateOf("4242") }
    var month by remember { mutableStateOf("12") }
    var year by remember { mutableStateOf((java.time.Year.now().value + 3).toString()) }
    val valid = last4.length == 4 &&
        (month.toIntOrNull()?.let { it in 1..12 } == true) &&
        (year.toIntOrNull()?.let { it in java.time.Year.now().value..(java.time.Year.now().value + 20) } == true)

    if (showAdd) AlertDialog(
        onDismissRequest = { if (!busy) showAdd = false },
        title = { Text("Add development card") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Use display details only. RideNova does not ask for or store a real card number or CVV in this development build.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("Visa", "Mastercard", "Amex").forEach { option ->
                        FilterChip(selected = brand == option, onClick = { brand = option }, label = { Text(option, fontSize = 11.sp) })
                    }
                }
                OutlinedTextField(last4, { last4 = it.filter(Char::isDigit).take(4) }, label = { Text("Last 4 display digits") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(month, { month = it.filter(Char::isDigit).take(2) }, modifier = Modifier.weight(1f), label = { Text("Month") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                    OutlinedTextField(year, { year = it.filter(Char::isDigit).take(4) }, modifier = Modifier.weight(1f), label = { Text("Year") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                onAddDevelopmentCard(brand, last4, month.toInt(), year.toInt())
                showAdd = false
            }, enabled = valid && !busy) { Text("Add") }
        },
        dismissButton = { TextButton(onClick = { showAdd = false }, enabled = !busy) { Text("Cancel") } }
    )

    Scaffold(
        topBar = { TopAppBar(title = { Text("Payment methods") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }) }
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
            Text("Choose how you’ll pay", fontSize = 25.sp, fontWeight = FontWeight.Bold)
            Text(if (staging) "Use a Stripe test card for test payments. Existing development references cannot be charged. No real money moves." else "Tap a card to select it for your rides. No real card is charged.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            errorMessage?.let { Spacer(Modifier.height(10.dp)); Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp) }
            if (busy) { Spacer(Modifier.height(12.dp)); LinearProgressIndicator(Modifier.fillMaxWidth()) }
            Spacer(Modifier.height(16.dp))
            methods.forEach { method ->
                val highlight by animateColorAsState(
                    targetValue = if (method.isDefault) MaterialTheme.colorScheme.primary.copy(alpha = .08f)
                    else MaterialTheme.colorScheme.surface,
                    animationSpec = tween(220), label = "payment card selection"
                )
                Surface(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)
                        .clickable(enabled = !busy && !method.isDefault) { onMakeDefault(method.id) },
                    shape = RoundedCornerShape(18.dp),
                    color = highlight,
                    border = androidx.compose.foundation.BorderStroke(
                        if (method.isDefault) 1.8.dp else 1.dp,
                        if (method.isDefault) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline.copy(alpha = .18f)
                    )
                ) {
                    Row(Modifier.padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.CreditCard, null, tint = NovaBlue)
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(method.displayLabel, fontWeight = FontWeight.SemiBold)
                            Text("Expires ${method.expiryMonth.toString().padStart(2, '0')}/${method.expiryYear} · ${if (method.developmentOnly) "Display reference" else "Stripe test card"}", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp)
                            if (method.isDefault) Text("Selected for rides", color = MaterialTheme.colorScheme.primary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                        }
                        if (method.isDefault) Icon(Icons.Default.CheckCircle, "Selected for rides", tint = MaterialTheme.colorScheme.primary)
                        if (methods.size > 1) IconButton(onClick = { onRemove(method.id) }, enabled = !busy) { Icon(Icons.Default.DeleteOutline, "Remove") }
                    }
                }
            }
            Spacer(Modifier.height(14.dp))
            if (fromBooking) {
                Button(
                    onClick = onReturnToBooking,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
                    enabled = !busy,
                    shape = RoundedCornerShape(16.dp)
                ) { Text("Continue to booking") }
                Spacer(Modifier.height(12.dp))
            }
            if (staging) {
                Button(onClick = onStartTestSetup, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp), enabled = !busy && methods.size < 5) { Text("Add Stripe test card") }
                if (pendingTestSetup) TextButton(onClick = onVerifyTestSetup, enabled = !busy) { Text("Verify test card after checkout") }
            } else Button(onClick = { showAdd = true }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp), enabled = backendMode && !busy && methods.size < 5, shape = RoundedCornerShape(16.dp)) {
                Icon(Icons.Default.AddCard, null); Spacer(Modifier.width(8.dp)); Text("Add development card")
            }
            Spacer(Modifier.height(12.dp))
            Surface(shape = RoundedCornerShape(16.dp), color = NovaBlue.copy(alpha = .10f)) {
                Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Security, null, tint = NovaBlue); Spacer(Modifier.width(10.dp))
                    Text("Stripe test checkout collects test card details. RideNova stores only provider references and display details; no raw card numbers or CVV.", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun SavedPlaceCard(
    slot: String,
    title: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    place: PlaceSuggestion?,
    onEdit: (String) -> Unit,
    onClear: (String) -> Unit
) {
    Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(44.dp).clip(CircleShape).background(NovaBlue.copy(alpha = .12f)), contentAlignment = Alignment.Center) {
                Icon(icon, null, tint = NovaBlue)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold)
                Text(place?.address ?: "Not set", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
            if (place != null) IconButton(onClick = { onClear(slot) }) { Icon(Icons.Default.DeleteOutline, "Remove $title") }
            TextButton(onClick = { onEdit(slot) }) { Text(if (place == null) "Add" else "Edit") }
        }
    }
}

@Composable
private fun AccountDetailScreen(title: String, description: String, onBack: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(22.dp)) {
            Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                Column(Modifier.fillMaxWidth().padding(20.dp)) {
                    Text(title, fontWeight = FontWeight.Bold, fontSize = 22.sp, color = MaterialTheme.colorScheme.onSurface)
                    Spacer(Modifier.height(8.dp))
                    Text(description, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 22.sp)
                }
            }
        }
    }
}

@Composable
private fun AppearanceScreen(
    themeMode: RideNovaThemeMode,
    onThemeModeChange: (RideNovaThemeMode) -> Unit,
    onBack: () -> Unit
) {
    val options = listOf(
        Triple(RideNovaThemeMode.DARK, "Dark", "Deep black RideNova interface and dark map"),
        Triple(RideNovaThemeMode.LIGHT, "Light", "Bright interface with the original RideNova look"),
        Triple(RideNovaThemeMode.SYSTEM, "Use device setting", "Automatically follows your phone appearance")
    )
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Appearance") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
            Text("Choose your RideNova look", fontSize = 25.sp, fontWeight = FontWeight.Bold)
            Text(
                "Your choice is saved on this device. Dark mode also applies a RideNova night style to Google Maps.",
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(18.dp))
            options.forEach { (mode, title, subtitle) ->
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 6.dp)
                        .clickable { onThemeModeChange(mode) },
                    shape = RoundedCornerShape(18.dp),
                    color = if (themeMode == mode) MaterialTheme.colorScheme.primary.copy(alpha = .12f)
                    else MaterialTheme.colorScheme.surfaceVariant,
                    border = if (themeMode == mode) androidx.compose.foundation.BorderStroke(1.5.dp, MaterialTheme.colorScheme.primary) else null
                ) {
                    Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            when (mode) {
                                RideNovaThemeMode.DARK -> Icons.Default.DarkMode
                                RideNovaThemeMode.LIGHT -> Icons.Default.LightMode
                                RideNovaThemeMode.SYSTEM -> Icons.Default.SettingsBrightness
                            },
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary
                        )
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(title, fontWeight = FontWeight.SemiBold)
                            Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                        }
                        RadioButton(selected = themeMode == mode, onClick = { onThemeModeChange(mode) })
                    }
                }
            }
        }
    }
}

@Composable
private fun LanguageScreen(onBack: () -> Unit) {
    var selected by remember { mutableStateOf("English") }
    val languages = listOf("English", "Français", "Español")
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.language)) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } }
            )
        }
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
            Text("App language", fontSize = 25.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
            Text("The localization framework is ready; live language switching will be connected in a later build.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(18.dp))
            languages.forEach { language ->
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).clickable { selected = language }.padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    RadioButton(selected = selected == language, onClick = { selected = language })
                    Spacer(Modifier.width(8.dp))
                    Text(language, fontWeight = FontWeight.Medium)
                }
            }
        }
    }
}


private fun topLevelDirection(from: String?, to: String?): Int {
    val order = mapOf(
        Routes.HOME to 0,
        Routes.TRIPS to 1,
        Routes.ACCOUNT to 2
    )
    val fromIndex = order[from] ?: return 0
    val toIndex = order[to] ?: return 0
    return toIndex.compareTo(fromIndex)
}

private fun navigateTopLevel(nav: NavHostController, route: String) {
    if (nav.currentDestination?.route == route) return
    // Keep exactly one top-level destination above Home. We intentionally do not
    // save/restore nested tab destinations here; restoring them could reopen a
    // child screen such as Appearance when the rider taps Trips or Account.
    nav.navigate(route) {
        launchSingleTop = true
        restoreState = false
        popUpTo(Routes.HOME) {
            inclusive = false
            saveState = false
        }
    }
}

@Composable
private fun BottomBar(nav: NavHostController, selectedRoute: String) {
    NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
        NavigationBarItem(
            selected = selectedRoute == Routes.HOME,
            onClick = { navigateTopLevel(nav, Routes.HOME) },
            icon = { Icon(Icons.Default.Home, null) },
            label = { Text(stringResource(R.string.home)) }
        )
        NavigationBarItem(
            selected = selectedRoute == Routes.TRIPS,
            onClick = { navigateTopLevel(nav, Routes.TRIPS) },
            icon = { Icon(Icons.Default.ReceiptLong, null) },
            label = { Text(stringResource(R.string.trips)) }
        )
        NavigationBarItem(
            selected = selectedRoute == Routes.ACCOUNT,
            onClick = { navigateTopLevel(nav, Routes.ACCOUNT) },
            icon = { Icon(Icons.Default.Person, null) },
            label = { Text(stringResource(R.string.account)) }
        )
    }
}

@Composable
private fun PrimaryButton(text: String, onClick: () -> Unit, enabled: Boolean = true) {
    Button(onClick, enabled = enabled, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp), shape = RoundedCornerShape(18.dp), colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) { Text(text, fontWeight = FontWeight.Bold, fontSize = 16.sp) }
}
