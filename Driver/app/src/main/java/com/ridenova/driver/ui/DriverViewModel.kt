package com.ridenova.driver.ui

import android.content.Context
import android.app.Application
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.android.gms.maps.model.LatLng
import com.ridenova.driver.data.DemoDriverRepository
import com.ridenova.driver.data.DriverRepository
import com.ridenova.driver.data.DriverLocationSource
import com.ridenova.driver.data.DriverSessionStore
import com.ridenova.driver.data.DriverProfileStore
import com.ridenova.driver.data.RemoteDriverRepository
import com.ridenova.driver.data.RestoredDriverSession
import com.ridenova.driver.BuildConfig
import com.ridenova.driver.R
import com.ridenova.driver.location.DriverLocationService
import com.ridenova.driver.model.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import kotlin.math.*

data class DriverUiState(
    val availability: DriverAvailability = DriverAvailability.OFFLINE,
    val rideStage: RideStage = RideStage.IDLE,
    val activeRide: RideRequest? = null,
    val driverLocation: LatLng = LatLng(49.1913, -122.8490),
    val deviceLocation: LatLng? = null,
    val locationPermissionGranted: Boolean = false,
    val backgroundLocationActive: Boolean = false,
    val nextStopDistanceKm: Double? = null,
    val nextStopEtaMin: Int? = null,
    val routeProgress: Float = 0f,
    val todayEarnings: Double = 0.0,
    val todayTrips: Int = 0,
    val onlineMinutes: Int = 0,
    val pinError: String? = null,
    val resumedRide: Boolean = false,
    val remoteMode: Boolean = false,
    val dispatchReason: String = "CHECKING",
    val category: String = "",
    val lastServerSyncMs: Long = 0L,
    val busy: Boolean = false,
    val connectionError: String? = null,
    val profile: DriverProfile = DriverProfile()
)

class DriverViewModel(application: Application) : AndroidViewModel(application) {
    private val fleetToken = com.ridenova.driver.data.FleetCredentials(application).load()
    private val remote = if (BuildConfig.RIDENOVA_DEV_URL.isNotBlank() &&
        (fleetToken.isNotBlank() || (BuildConfig.RIDENOVA_LEGACY_DRIVER && BuildConfig.RIDENOVA_DEV_TOKEN.isNotBlank())))
        RemoteDriverRepository(application, BuildConfig.RIDENOVA_DEV_URL,
            fleetToken.ifBlank { BuildConfig.RIDENOVA_DEV_TOKEN }, fleetToken.isNotBlank()) else null
    private val repository: DriverRepository = remote ?: DemoDriverRepository(application)
    private val sessionStore = DriverSessionStore(application)
    private val profileStore = DriverProfileStore(application)
    private val restored = if (remote == null) sessionStore.restore() else
        RestoredDriverSession(DriverAvailability.OFFLINE, RideStage.IDLE, null)

    private val _uiState = MutableStateFlow(DriverUiState(
        availability = if (restored.ride != null) DriverAvailability.ONLINE else DriverAvailability.OFFLINE,
        rideStage = restored.stage,
        activeRide = restored.ride,
        resumedRide = restored.ride != null && restored.stage !in setOf(RideStage.IDLE, RideStage.COMPLETED),
        profile = profileStore.load(),
        remoteMode = remote != null,
        connectionError = if (BuildConfig.RIDENOVA_DEV_URL.isNotBlank() && remote == null)
            "Check RIDENOVA_DEV_URL and RIDENOVA_DEV_TOKEN in local.properties, then rebuild" else null
    ))
    val uiState: StateFlow<DriverUiState> = _uiState.asStateFlow()
    val completedTrips = repository.completedTrips

    private var simulationJob: Job? = null
    private var locationJob: Job? = null
    private var requestJob: Job? = null
    private var onlineTimerJob: Job? = null
    private var availabilityRevision = 0L
    private var lastLocationPublishAt: Long = 0L
    private var lastPresencePublishAt: Long = 0L
    private var requestTonePlayer: MediaPlayer? = null
    private var soundingRideId: String? = null

    init {
        if (remote == null) viewModelScope.launch {
            uiState.map { Triple(it.availability, it.rideStage, it.activeRide?.id) }
                .distinctUntilChanged().collect {
                    val state = uiState.value
                    sessionStore.save(state.availability, state.rideStage, state.activeRide)
                }
        }
        remote?.let { backend ->
            viewModelScope.launch {
                backend.error.collect { error ->
                    if (error != null) _uiState.update { it.copy(connectionError = error) }
                }
            }
            viewModelScope.launch { runCatching { backend.refreshCompletedTrips() } }
            viewModelScope.launch {
                while (true) {
                    if (!_uiState.value.busy) {
                        val revision = availabilityRevision
                        val stage = _uiState.value.rideStage
                        try {
                            val status = backend.serverStatus()
                            val active = if (status.activeRideId != null) backend.restoreActive() else null
                            if (!_uiState.value.busy && revision == availabilityRevision && stage == _uiState.value.rideStage) {
                                val wasOnline = _uiState.value.availability == DriverAvailability.ONLINE
                                val online = status.online || active != null
                                val hadActive = stage in setOf(RideStage.ACCEPTED, RideStage.ARRIVING, RideStage.ARRIVED, RideStage.ON_TRIP)
                                val nextStage = active?.second ?: if (!online || hadActive) RideStage.IDLE else stage
                                profileStore.save(status.profile)
                                _uiState.update { current -> current.copy(
                                    availability = if (online) DriverAvailability.ONLINE else DriverAvailability.OFFLINE,
                                    driverLocation = if (current.deviceLocation == null && status.locationAgeSeconds?.let { it <= 30 } == true) status.lastLocation ?: current.driverLocation else current.driverLocation,
                                    profile = status.profile, dispatchReason = status.dispatchReason, category = status.category,
                                    lastServerSyncMs = System.currentTimeMillis(), connectionError = null,
                                    activeRide = active?.first ?: if (!online || hadActive) null else current.activeRide,
                                    rideStage = nextStage,
                                    resumedRide = active != null && current.activeRide?.id != active.first.id
                                ) }
                                if (active != null || !online) {
                                    requestJob?.cancel(); repository.clearIncomingRide(); stopRequestTone()
                                }
                                if (online) {
                                    if (!wasOnline) startOnlineTimer()
                                    if (com.ridenova.driver.location.DriverVisibility.foreground) startBackgroundLocationIfAllowed()
                                    if (active == null && requestJob?.isActive != true) restartRemotePolling()
                                } else {
                                    onlineTimerJob?.cancel()
                                    DriverLocationService.stop(getApplication<Application>())
                                    _uiState.update { it.copy(backgroundLocationActive = false) }
                                }
                            }
                        } catch (ex: CancellationException) { throw ex }
                        catch (ex: Exception) {
                            if (revision == availabilityRevision) _uiState.update { it.copy(connectionError = ex.localizedMessage) }
                        }
                    }
                    delay(3_000)
                }
            }
        }
        if (restored.ride != null && restored.stage !in setOf(RideStage.IDLE, RideStage.COMPLETED)) {
            startOnlineTimer()
        }
        viewModelScope.launch {
            completedTrips.collect { trips ->
                val today = LocalDate.now()
                val todaysTrips = trips.filter {
                    Instant.ofEpochMilli(it.completedAtEpochMs).atZone(ZoneId.systemDefault()).toLocalDate() == today
                }
                _uiState.update { it.copy(todayTrips = todaysTrips.size,
                    todayEarnings = todaysTrips.sumOf(CompletedTrip::driverEarningsCad)) }
            }
        }
        viewModelScope.launch {
            combine(repository.incomingRide, _uiState.map { it.busy to it.availability }.distinctUntilChanged()) { request, _ -> request }.collect { request ->
                if (_uiState.value.busy) return@collect
                if (request != null && _uiState.value.availability == DriverAvailability.ONLINE &&
                    _uiState.value.rideStage in setOf(RideStage.IDLE, RideStage.REQUESTED, RideStage.COMPLETED)) {
                    val previous = _uiState.value.activeRide
                    _uiState.update { it.copy(activeRide = request, rideStage = RideStage.REQUESTED) }
                    if (previous?.id != request.id || previous?.expiresAtEpochMs != request.expiresAtEpochMs) {
                        stopRequestTone()
                        if (com.ridenova.driver.location.DriverVisibility.foreground) startRequestTone(request.id)
                    }
                } else if (remote != null && request == null && _uiState.value.rideStage == RideStage.REQUESTED) {
                    stopRequestTone()
                    _uiState.update { it.copy(activeRide = null, rideStage = RideStage.IDLE) }
                }
            }
        }
    }

    fun toggleOnline() {
        // The driver must remain reachable until this trip is completed.
        if (_uiState.value.rideStage in setOf(RideStage.ACCEPTED, RideStage.ARRIVING, RideStage.ARRIVED, RideStage.ON_TRIP)) return
        if (_uiState.value.busy) return
        availabilityRevision++
        val goingOnline = _uiState.value.availability == DriverAvailability.OFFLINE
        if (!goingOnline) stopRequestTone()
        if (remote != null) {
            _uiState.update { it.copy(busy = true) }
            viewModelScope.launch {
                runCatching { remote.setOnline(goingOnline, _uiState.value.profile) }.onSuccess {
                    requestJob?.cancel()
                    repository.clearIncomingRide()
                    _uiState.update { it.copy(busy = false, connectionError = null,
                        availability = if (goingOnline) DriverAvailability.ONLINE else DriverAvailability.OFFLINE,
                        activeRide = null, rideStage = RideStage.IDLE) }
                    if (goingOnline) {
                        startOnlineTimer()
                        startBackgroundLocationIfAllowed()
                        requestJob = viewModelScope.launch { repository.requestNextRide() }
                    } else {
                        onlineTimerJob?.cancel()
                        DriverLocationService.stop(getApplication<Application>())
                        _uiState.update { it.copy(backgroundLocationActive = false) }
                    }
                }.onFailure { ex -> _uiState.update { it.copy(busy = false, connectionError = ex.localizedMessage) } }
            }
            return
        }
        requestJob?.cancel()
        _uiState.update {
            it.copy(
                availability = if (goingOnline) DriverAvailability.ONLINE else DriverAvailability.OFFLINE,
                rideStage = if (goingOnline) it.rideStage else RideStage.IDLE,
                activeRide = if (goingOnline) it.activeRide else null,
                routeProgress = 0f
            )
        }
        simulationJob?.cancel()
        if (goingOnline) {
            startOnlineTimer()
            requestJob = viewModelScope.launch { repository.requestNextRide() }
        } else {
            onlineTimerJob?.cancel()
            viewModelScope.launch { repository.clearIncomingRide() }
        }
    }

    private fun startBackgroundLocationIfAllowed() {
        if (remote == null || !_uiState.value.locationPermissionGranted ||
            _uiState.value.availability != DriverAvailability.ONLINE) return
        runCatching { DriverLocationService.start(getApplication<Application>()) }
            .onSuccess { _uiState.update { it.copy(backgroundLocationActive = true) } }
            .onFailure { ex -> _uiState.update { it.copy(connectionError = ex.localizedMessage) } }
    }

    private fun haversineKm(a: LatLng, b: LatLng): Double {
        val r = 6371.0088
        val p1 = Math.toRadians(a.latitude)
        val p2 = Math.toRadians(b.latitude)
        val dp = Math.toRadians(b.latitude - a.latitude)
        val dl = Math.toRadians(b.longitude - a.longitude)
        val h = sin(dp / 2).pow(2) + cos(p1) * cos(p2) * sin(dl / 2).pow(2)
        return r * 2 * atan2(sqrt(h), sqrt(1 - h))
    }

    fun updateDemoProfile(name: String, vehicle: String, plate: String) {
        if (name.isBlank() || vehicle.isBlank() || plate.isBlank()) return
        val profile = _uiState.value.profile.copy(name = name.trim(), vehicle = vehicle.trim(), plate = plate.trim())
        if (remote == null) {
            profileStore.save(profile)
            _uiState.update { it.copy(profile = profile) }
        } else viewModelScope.launch {
            try {
                remote.updateProfile(profile, _uiState.value.availability == DriverAvailability.ONLINE)
                profileStore.save(profile)
                _uiState.update { it.copy(profile = profile, connectionError =
                    if (fleetToken.isNotBlank()) "Profile saved. Admin must review your documents and approve the changes." else null) }
            } catch (ex: CancellationException) { throw ex }
            catch (ex: Exception) { _uiState.update { it.copy(connectionError = ex.localizedMessage) } }
        }
    }

    private fun startOnlineTimer() {
        onlineTimerJob?.cancel()
        onlineTimerJob = viewModelScope.launch {
            while (true) { delay(60_000); _uiState.update { it.copy(onlineMinutes = it.onlineMinutes + 1) } }
        }
    }

    /** Device GPS is used on the idle map. Demo trip movement is explicitly simulated. */
    fun startDeviceLocation(context: Context, permissionGranted: Boolean) {
        _uiState.update { it.copy(locationPermissionGranted = permissionGranted) }
        if (remote != null && _uiState.value.availability == DriverAvailability.ONLINE &&
            _uiState.value.rideStage in setOf(RideStage.IDLE, RideStage.REQUESTED, RideStage.COMPLETED)) restartRemotePolling()
        if (_uiState.value.rideStage == RideStage.REQUESTED) _uiState.value.activeRide?.let { startRequestTone(it.id) }
        if (permissionGranted && remote != null && _uiState.value.availability == DriverAvailability.ONLINE) {
            startBackgroundLocationIfAllowed()
        }
        locationJob?.cancel()
        if (!permissionGranted) return
        locationJob = viewModelScope.launch {
            DriverLocationSource(context.applicationContext).locations().collect { point ->
                _uiState.update { current ->
                    val ride = current.activeRide
                    val next = when (current.rideStage) {
                        RideStage.ACCEPTED, RideStage.ARRIVING, RideStage.ARRIVED -> ride?.pickup
                        RideStage.ON_TRIP -> ride?.destination
                        else -> null
                    }
                    val distance = next?.let { haversineKm(point, it) }
                    val speed = if (current.rideStage == RideStage.ON_TRIP) 36.0 else 28.0
                    val eta = distance?.let { if (it <= 0.15) 1 else max(2, ceil((it / speed) * 60.0 + 1.0).toInt()) }
                    val progress = if (ride != null && current.rideStage == RideStage.ON_TRIP && distance != null)
                        (1.0 - distance / max(0.1, ride.tripDistanceKm)).coerceIn(0.0, 1.0).toFloat()
                    else current.routeProgress
                    current.copy(
                        deviceLocation = point,
                        driverLocation = if (remote != null || current.rideStage == RideStage.IDLE) point else current.driverLocation,
                        nextStopDistanceKm = distance,
                        nextStopEtaMin = eta,
                        routeProgress = progress
                    )
                }
                val ride = _uiState.value.activeRide
                val stamp = System.currentTimeMillis()
                if (remote != null && _uiState.value.availability == DriverAvailability.ONLINE &&
                    stamp - lastPresencePublishAt >= 10_000L) {
                    lastPresencePublishAt = stamp
                    viewModelScope.launch {
                        runCatching { remote.publishPresence(point) }
                            .onFailure { ex -> if (ex !is CancellationException) _uiState.update { it.copy(connectionError = ex.localizedMessage) } }
                    }
                }
                if (remote != null && ride != null && _uiState.value.rideStage in
                    setOf(RideStage.ACCEPTED, RideStage.ARRIVING, RideStage.ARRIVED, RideStage.ON_TRIP) &&
                    stamp - lastLocationPublishAt >= 5_000L) {
                    lastLocationPublishAt = stamp
                    viewModelScope.launch {
                        runCatching { remote.publish(ride.id, point) }
                            .onFailure { ex -> if (ex !is CancellationException) _uiState.update { it.copy(connectionError = ex.localizedMessage) } }
                    }
                }
            }
        }
    }

    fun stopDeviceLocation() {
        stopRequestTone()
        locationJob?.cancel()
        locationJob = null
    }

    fun acceptRide() {
        if (_uiState.value.rideStage != RideStage.REQUESTED) return
        stopRequestTone()
        val ride = _uiState.value.activeRide ?: return
        if (remote != null) {
            remoteTransition("accept", RideStage.ARRIVING) {
                requestJob?.cancel()
                repository.clearIncomingRide()
            }
            return
        }
        // Demo requests are in Surrey; don't draw a fake cross-country trip from device GPS.
        val origin = _uiState.value.driverLocation.let { point ->
            if (kotlin.math.abs(point.latitude - ride.pickup.latitude) > 0.2 ||
                kotlin.math.abs(point.longitude - ride.pickup.longitude) > 0.2
            ) LatLng(49.1913, -122.8490) else point
        }
        _uiState.update { it.copy(driverLocation = origin) }
        _uiState.update { it.copy(rideStage = RideStage.ACCEPTED, routeProgress = 0f, resumedRide = false) }
        simulateMovement(from = origin, to = ride.pickup, targetStage = RideStage.ARRIVING)
    }

    fun declineRide() {
        if (_uiState.value.rideStage != RideStage.REQUESTED) return
        stopRequestTone()
        if (remote != null) {
            remoteTransition("decline", RideStage.IDLE) { restartRemotePolling() }
            return
        }
        requestJob?.cancel()
        _uiState.update { it.copy(activeRide = null, rideStage = RideStage.IDLE) }
        requestJob = viewModelScope.launch {
            repository.clearIncomingRide()
            delay(1200)
            if (_uiState.value.availability == DriverAvailability.ONLINE) repository.requestNextRide()
        }
    }

    fun markArrived() {
        if (_uiState.value.rideStage !in setOf(RideStage.ACCEPTED, RideStage.ARRIVING)) return
        val pickup = _uiState.value.activeRide?.pickup ?: return
        if (remote != null) { remoteTransition("arrive", RideStage.ARRIVED); return }
        simulationJob?.cancel()
        _uiState.update { it.copy(rideStage = RideStage.ARRIVED, driverLocation = pickup, routeProgress = 1f, resumedRide = false) }
    }

    fun startTrip(pin: String) {
        if (_uiState.value.rideStage != RideStage.ARRIVED) return
        if (remote != null) { remoteTransition("start", RideStage.ON_TRIP, pin); return }
        if (pin.trim() != "5824") {
            _uiState.update { it.copy(pinError = "Check the 4-digit demo pickup PIN") }
            return
        }
        val ride = _uiState.value.activeRide ?: return
        _uiState.update { it.copy(rideStage = RideStage.ON_TRIP, routeProgress = 0f, pinError = null, resumedRide = false) }
        simulateMovement(from = ride.pickup, to = ride.destination, targetStage = RideStage.ON_TRIP)
    }

    fun completeTrip() {
        if (_uiState.value.rideStage != RideStage.ON_TRIP) return
        val ride = _uiState.value.activeRide ?: return
        if (remote != null) {
            remoteTransition("complete", RideStage.COMPLETED) {
                remote.refreshCompletedTrips()
            }
            return
        }
        simulationJob?.cancel()
        _uiState.update {
            it.copy(
                rideStage = RideStage.COMPLETED,
                driverLocation = ride.destination,
                routeProgress = 1f,
                resumedRide = false
            )
        }
        viewModelScope.launch { repository.saveCompletedRide(ride) }
    }

    fun cancelDemoTrip() {
        if (_uiState.value.rideStage !in setOf(RideStage.ACCEPTED, RideStage.ARRIVING, RideStage.ARRIVED, RideStage.ON_TRIP)) return
        if (remote != null) { remoteTransition("cancel", RideStage.IDLE) { restartRemotePolling() }; return }
        simulationJob?.cancel()
        requestJob?.cancel()
        _uiState.update { it.copy(rideStage = RideStage.IDLE, activeRide = null,
            routeProgress = 0f, pinError = null, resumedRide = false) }
        requestJob = viewModelScope.launch {
            repository.clearIncomingRide()
            delay(1200)
            if (_uiState.value.availability == DriverAvailability.ONLINE && _uiState.value.rideStage == RideStage.IDLE) {
                repository.requestNextRide()
            }
        }
    }

    fun dismissCompleted() {
        if (_uiState.value.rideStage != RideStage.COMPLETED) return
        _uiState.update { it.copy(rideStage = RideStage.IDLE, activeRide = null, routeProgress = 0f) }
        if (_uiState.value.availability == DriverAvailability.ONLINE) {
            requestJob?.cancel()
            requestJob = viewModelScope.launch {
                delay(1200)
                if (_uiState.value.availability == DriverAvailability.ONLINE && _uiState.value.rideStage == RideStage.IDLE) repository.requestNextRide()
            }
        }
    }

    fun simulateIncomingRequest() {
        if (_uiState.value.availability == DriverAvailability.ONLINE && _uiState.value.rideStage == RideStage.IDLE) {
            requestJob?.cancel()
            requestJob = viewModelScope.launch { repository.requestNextRide() }
        }
    }

    private fun startRequestTone(rideId: String) {
        // Do not restart the sound on every polling refresh for the same offer.
        if (soundingRideId == rideId && requestTonePlayer?.isPlaying == true) return
        stopRequestTone()
        soundingRideId = rideId
        requestTonePlayer = runCatching {
            val attributes = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
            MediaPlayer.create(
                getApplication<Application>(),
                R.raw.nova_ride_request,
                attributes,
                AudioManager.AUDIO_SESSION_ID_GENERATE
            )?.apply {
                isLooping = true
                setOnErrorListener { player, _, _ ->
                    runCatching { player.stop() }
                    player.release()
                    requestTonePlayer = null
                    soundingRideId = null
                    true
                }
                start()
            }
        }.getOrNull()
    }

    private fun stopRequestTone() {
        requestTonePlayer?.let { player ->
            runCatching { if (player.isPlaying) player.stop() }
            player.release()
        }
        requestTonePlayer = null
        soundingRideId = null
    }

    fun signOut(onSignedOut: () -> Unit) {
        if (_uiState.value.busy || fleetToken.isBlank()) return
        availabilityRevision++
        _uiState.update { it.copy(busy = true, connectionError = null) }
        viewModelScope.launch {
            try {
                try {
                    com.ridenova.driver.data.DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL, fleetToken, true)
                        .json("POST", "v2/fleet/driver/logout", org.json.JSONObject())
                } catch (ex: com.ridenova.driver.data.DriverApiException) {
                    // A revoked session can be removed locally, including after a lost logout response.
                    if (ex.status != 401) throw ex
                }
                requestJob?.cancel()
                locationJob?.cancel()
                onlineTimerJob?.cancel()
                simulationJob?.cancel()
                stopRequestTone()
                DriverLocationService.stop(getApplication<Application>())
                kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                    com.ridenova.driver.data.FleetCredentials(getApplication<Application>()).clear()
                }
                onSignedOut()
            } catch (ex: CancellationException) { throw ex }
            catch (ex: Exception) { _uiState.update { it.copy(busy = false, connectionError = ex.localizedMessage) } }
        }
    }

    override fun onCleared() {
        stopRequestTone()
        super.onCleared()
    }

    private fun restartRemotePolling() {
        requestJob?.cancel()
        requestJob = viewModelScope.launch { repository.requestNextRide() }
    }

    private fun remoteTransition(action: String, next: RideStage, pin: String? = null,
                                 onSuccess: suspend () -> Unit = {}) {
        val backend = remote ?: return
        val ride = _uiState.value.activeRide ?: return
        if (_uiState.value.busy) return
        availabilityRevision++
        _uiState.update { it.copy(busy = true, connectionError = null, pinError = null) }
        viewModelScope.launch {
            runCatching { backend.action(ride.id, action, pin) }.onSuccess {
                repository.clearIncomingRide()
                com.ridenova.driver.location.DriverAlerts.clear(getApplication<Application>())
                _uiState.update { state -> state.copy(busy = false, rideStage = next,
                    activeRide = if (next == RideStage.IDLE) null else ride,
                    routeProgress = if (next == RideStage.COMPLETED) 1f else 0f,
                    resumedRide = false) }
                try { onSuccess() }
                catch (ex: CancellationException) { throw ex }
                catch (ex: Exception) { _uiState.update { it.copy(connectionError = "Trip updated; refresh failed: " + ex.localizedMessage) } }
            }.onFailure { ex ->
                if (ex is CancellationException) return@onFailure
                _uiState.update { state -> state.copy(busy = false,
                    connectionError = ex.localizedMessage,
                    pinError = if (action == "start") ex.localizedMessage else null) }
                // If accept/decline failed and the same offer is still active, resume its alert.
                if (action in setOf("accept", "decline") && _uiState.value.rideStage == RideStage.REQUESTED) {
                    startRequestTone(ride.id)
                }
            }
        }
    }

    private fun simulateMovement(from: LatLng, to: LatLng, targetStage: RideStage) {
        simulationJob?.cancel()
        simulationJob = viewModelScope.launch {
            if (targetStage == RideStage.ARRIVING) {
                _uiState.update { it.copy(rideStage = RideStage.ARRIVING) }
            }
            val steps = 80
            repeat(steps + 1) { index ->
                val p = index / steps.toFloat()
                val lat = from.latitude + (to.latitude - from.latitude) * p
                val lng = from.longitude + (to.longitude - from.longitude) * p
                _uiState.update { it.copy(driverLocation = LatLng(lat, lng), routeProgress = p) }
                delay(250)
            }
        }
    }
}
