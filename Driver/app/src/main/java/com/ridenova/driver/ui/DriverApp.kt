package com.ridenova.driver.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.runtime.saveable.rememberSaveable
import kotlinx.coroutines.async
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.semantics.*
import androidx.compose.foundation.horizontalScroll
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.LatLngBounds
import com.google.maps.android.compose.*
import com.ridenova.driver.BuildConfig
import com.ridenova.driver.model.*
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import com.ridenova.driver.navigation.DriverRoadRoutes
import com.ridenova.driver.navigation.RoadRoute
import com.google.android.gms.maps.model.*
import android.location.Location
import java.text.NumberFormat
import java.util.Locale

private enum class DriverTab(val label: String) {
    HOME("Home"), EARNINGS("Earnings"), HISTORY("Trips"), ACCOUNT("Account"), ALERTS("Alerts & shortcut")
}

@Composable
fun RideNovaDriverApp(locationGranted: Boolean, viewModel: DriverViewModel = viewModel(), onSignedOut: () -> Unit = {}) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner, locationGranted) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> viewModel.startDeviceLocation(context, locationGranted)
                Lifecycle.Event.ON_STOP -> viewModel.stopDeviceLocation()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        if (lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
            viewModel.startDeviceLocation(context, locationGranted)
        }
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            viewModel.stopDeviceLocation()
        }
    }
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val trips by viewModel.completedTrips.collectAsStateWithLifecycle()
    var selectedTab by rememberSaveable { mutableStateOf(DriverTab.HOME) }
    var inAppNavigation by remember { mutableStateOf(false) }
    var documents by rememberSaveable { mutableStateOf(false) }
    var access by rememberSaveable { mutableStateOf(false) }
    var selectedTrip by remember { mutableStateOf<CompletedTrip?>(null) }
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val requestVisible = state.rideStage == RideStage.REQUESTED && state.activeRide != null
    LaunchedEffect(state.rideStage) {
        if (state.rideStage !in setOf(RideStage.ACCEPTED, RideStage.ARRIVING, RideStage.ARRIVED, RideStage.ON_TRIP)) inAppNavigation = false
        if (state.rideStage in setOf(RideStage.ACCEPTED, RideStage.ARRIVING)) selectedTab = DriverTab.HOME
        if (requestVisible) drawer.close()
    }
    BackHandler(inAppNavigation) { inAppNavigation = false }
    BackHandler(selectedTrip != null) { selectedTrip = null }
    BackHandler(!inAppNavigation && !requestVisible && selectedTab != DriverTab.HOME && selectedTrip == null && !documents && !access) { selectedTab = DriverTab.HOME }
    // Build 32: the map owns horizontal gestures. The drawer is menu-button only so a
    // left/right map pan can never be interpreted as opening the navigation panel.
    ModalNavigationDrawer(drawerState = drawer, gesturesEnabled = false,
        drawerContent = {
            ModalDrawerSheet {
                Column(Modifier.fillMaxHeight().verticalScroll(rememberScrollState())) {
                    Row(Modifier.padding(start=24.dp,top=28.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(12.dp)) { NovaBrand(44);Column { Text("RideNova",style=MaterialTheme.typography.titleLarge);Text("DRIVER",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.primary) } }
                    Text(state.profile.name, Modifier.padding(start = 24.dp, top = 6.dp, bottom = 24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    DriverTab.entries.forEach { tab ->
                        NavigationDrawerItem(selected = selectedTab == tab,
                            label = { Text(tab.label) },
                            icon = { Icon(when(tab) {
                                DriverTab.HOME -> Icons.Default.Home
                                DriverTab.EARNINGS -> Icons.Default.Payments
                                DriverTab.HISTORY -> Icons.Default.ReceiptLong
                                DriverTab.ACCOUNT -> Icons.Default.Person
                                DriverTab.ALERTS -> Icons.Default.Notifications
                            }, null) },
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                            onClick = { selectedTab = tab; selectedTrip = null; documents = false; access = false; scope.launch { drawer.close() } })
                    }
                    HorizontalDivider(Modifier.padding(20.dp))
                    Text("Build 42.1 · ${BuildConfig.RIDENOVA_ENVIRONMENT}", Modifier.padding(24.dp), style = MaterialTheme.typography.bodySmall)
                }
            }
        }) {
        Scaffold(topBar = {
            if ((selectedTab != DriverTab.HOME || state.rideStage != RideStage.IDLE) && !requestVisible && !inAppNavigation) Surface {
                Row(Modifier.fillMaxWidth().statusBarsPadding().heightIn(min = 56.dp).padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = { scope.launch { drawer.open() } }) { Icon(Icons.Default.Menu, "Open driver menu") }
                    Text(if (selectedTab == DriverTab.HOME) "Your trip" else selectedTab.label, style = MaterialTheme.typography.titleLarge)
                }
            }
        },bottomBar={
            if(!requestVisible && !inAppNavigation && !documents && !access && selectedTrip==null && state.rideStage in setOf(RideStage.IDLE,RideStage.COMPLETED)) {
                NavigationBar(containerColor=MaterialTheme.colorScheme.surface,tonalElevation=0.dp) {
                    listOf(DriverTab.HOME,DriverTab.EARNINGS,DriverTab.HISTORY,DriverTab.ACCOUNT).forEach { tab ->
                        NavigationBarItem(selected=selectedTab==tab,onClick={selectedTab=tab},label={Text(tab.label)},icon={
                            Icon(when(tab) { DriverTab.HOME->Icons.Default.Home;DriverTab.EARNINGS->Icons.Default.Payments;DriverTab.HISTORY->Icons.Default.ReceiptLong;else->Icons.Default.Person },null)
                        })
                    }
                }
            }
        }) { padding ->
            Box(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
                if (inAppNavigation && state.activeRide != null) {
                    DriverNavigationScreen(state, onExit = { inAppNavigation = false }, onOpenGoogleMaps = {
                        openNavigation(context, if (state.rideStage == RideStage.ON_TRIP) state.activeRide!!.destination else state.activeRide!!.pickup)
                    })
                } else if (requestVisible) {
                    DedicatedRequestScreen(state, state.activeRide!!, viewModel::acceptRide, viewModel::declineRide)
                } else when (selectedTab) {
                    DriverTab.HOME -> DriverHomeScreen(state, viewModel, onInAppNavigate = { inAppNavigation = true },
                        onMenu = { scope.launch { drawer.open() } }, onEarnings = { selectedTab = DriverTab.EARNINGS },
                        onAlerts = { selectedTab = DriverTab.ALERTS })
                    DriverTab.EARNINGS -> EarningsScreen(state,trips) { selectedTrip=it;selectedTab=DriverTab.HISTORY }
                    DriverTab.HISTORY -> selectedTrip?.let { DriverTripDetailScreen(it) { selectedTrip = null } }
                        ?: TripHistoryScreen(trips, { selectedTab = DriverTab.HOME }, { selectedTrip = it })
                    DriverTab.ALERTS -> DriverAlertSettings()
                    DriverTab.ACCOUNT -> {
                        if (documents) FleetDocuments(onBack = { documents = false })
                        else if (access) FleetAccount(viewModel, onSignedOut, onBack = { access = false })
                        else AccountScreen(state.profile, trips.size, viewModel::updateDemoProfile,
                            fleet = com.ridenova.driver.data.FleetCredentials(context).load().isNotBlank(),
                            onDocuments = { documents = true }, onAccess = { access = true })
                    }
                }
            }
        }
    }
}

@Composable
private fun DriverHomeScreen(state: DriverUiState, viewModel: DriverViewModel, onInAppNavigate: () -> Unit,
    onMenu: () -> Unit, onEarnings: () -> Unit, onAlerts: () -> Unit) {
    val context = LocalContext.current
    var showSafety by remember { mutableStateOf(false) }
    var confirmCancel by remember { mutableStateOf(false) }
    if (state.rideStage == RideStage.IDLE) DriverIdleHome(state, viewModel::toggleOnline, viewModel::simulateIncomingRequest, onMenu, onEarnings, onAlerts)
    else DriverMapLayout(state) {
        if (state.activeRide != null && state.rideStage in setOf(RideStage.ACCEPTED, RideStage.ARRIVING, RideStage.ARRIVED, RideStage.ON_TRIP)) {
            ActiveRideCard(state, state.activeRide, viewModel::markArrived, viewModel::startTrip,
                viewModel::completeTrip, { onInAppNavigate() }, { showSafety = true }, { confirmCancel = true })
        } else Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            state.connectionError?.let { DriverNotice("Connection needs attention", it, true) }
            if (state.resumedRide) DriverNotice("Trip restored", "Your active trip is ready to continue.")
            when (state.rideStage) {
                RideStage.COMPLETED -> state.activeRide?.let { CompletedRideCard(it, state.remoteMode, viewModel::dismissCompleted) }
                else -> Unit
            }
        }
    }
    if (showSafety) {
        val ride = state.activeRide
        AlertDialog(
            onDismissRequest = { showSafety = false },
            title = { Text("Trip safety") },
            text = { Text("Share trip details with someone you trust. If there is an emergency in Canada, call 911.") },
            confirmButton = {
                TextButton(onClick = {
                    showSafety = false
                    if (ride != null) shareTrip(context, ride, state.deviceLocation, state.remoteMode)
                }) { Text("Share details") }
            },
            dismissButton = { TextButton(onClick = { showSafety = false }) { Text("Close") } }
        )
    }
    if (confirmCancel) {
        AlertDialog(
            onDismissRequest = { confirmCancel = false },
            title = { Text(if (state.remoteMode) "Cancel this driver assignment?" else "Cancel this demo trip?") },
            text = { Text(if (state.remoteMode)
                "The local server will return this request to the search queue. No payment or payout occurs."
                else "The simulated trip will end without earnings. This does not cancel a passenger booking in the other app.") },
            confirmButton = {
                TextButton(onClick = { confirmCancel = false; viewModel.cancelDemoTrip() }) {
                    Text("Cancel trip")
                }
            },
            dismissButton = { TextButton(onClick = { confirmCancel = false }) { Text("Keep trip") } }
        )
    }
}

/** Map and controls get independent space: neither can cover the other. */
@Composable
private fun DriverMapLayout(state: DriverUiState, content: @Composable () -> Unit) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        if (maxWidth > maxHeight && maxWidth >= 600.dp) {
            Row(Modifier.fillMaxSize()) {
                Box(Modifier.weight(1f).fillMaxHeight()) { DriverMap(state) }
                Surface(Modifier.weight(1f).fillMaxHeight()) { content() }
            }
        } else {
            val mapFraction = if (maxHeight < 420.dp) 0.25f else if (state.rideStage == RideStage.REQUESTED) 0.5f else 0.42f
            Column(Modifier.fillMaxSize()) {
                Box(Modifier.fillMaxWidth().weight(mapFraction)) { DriverMap(state) }
                Surface(Modifier.fillMaxWidth().weight(1f - mapFraction), shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp)) { content() }
            }
        }
    }
}

@Composable
private fun DriverNotice(title: String, message: String, error: Boolean = false) {
    NovaNotice(title,message,error)
}

@Composable
private fun DriverMap(state: DriverUiState, bottomInset: Dp = 0.dp, topInset: Dp = 0.dp) {
    val context = LocalContext.current
    val ride = state.activeRide
    val preview = state.rideStage == RideStage.REQUESTED
    val dropoff = state.rideStage in setOf(RideStage.ON_TRIP, RideStage.COMPLETED)
    var route by remember(ride?.id, preview, dropoff) { mutableStateOf<RoadRoute?>(null) }
    var pickupRoute by remember(ride?.id, preview, dropoff) { mutableStateOf<RoadRoute?>(null) }
    var loading by remember(ride?.id, preview, dropoff) { mutableStateOf(ride != null) }
    var routeFailed by remember(ride?.id, preview, dropoff) { mutableStateOf(false) }
    var retry by remember { mutableIntStateOf(0) }
    val currentPosition by rememberUpdatedState(state.driverLocation)
    LaunchedEffect(ride?.id, preview, dropoff, retry) {
        if (ride == null) { loading = false; return@LaunchedEffect }
        do {
            loading = route == null
            val pickup = if (preview) async { DriverRoadRoutes.fetch(context, currentPosition, ride.pickup) } else null
            val main = DriverRoadRoutes.fetch(context,
                if (preview) ride.pickup else currentPosition,
                if (preview || dropoff) ride.destination else ride.pickup)
            route = main.getOrNull()
            val pickupResult = pickup?.await()
            pickupRoute = pickupResult?.getOrNull()
            routeFailed = main.isFailure || pickupResult?.isFailure == true
            loading = false
            if (!preview) delay(30_000)
        } while (!preview)
    }
    val camera = rememberCameraPositionState { position = CameraPosition.fromLatLngZoom(state.driverLocation, 13.5f) }
    var loaded by remember { mutableStateOf(false) }
    var fit by remember { mutableIntStateOf(0) }
    var userMovedCamera by remember(ride?.id, preview, dropoff) { mutableStateOf(false) }
    val smoothDriverLocation = rememberSmoothLatLng(state.driverLocation)

    // A user gesture takes ownership of the camera until the explicit recenter button is tapped.
    // This prevents GPS/route refreshes from tugging the map back while the driver is panning.
    LaunchedEffect(camera) {
        snapshotFlow { camera.cameraMoveStartedReason }.collect { reason ->
            if (reason == CameraMoveStartedReason.GESTURE) userMovedCamera = true
        }
    }
    LaunchedEffect(loaded, ride?.id, preview, dropoff, route, pickupRoute, fit, bottomInset, topInset,
        if (ride == null && !userMovedCamera) state.driverLocation else null, userMovedCamera) {
        if (!loaded || userMovedCamera) return@LaunchedEffect
        val points = buildList {
            add(state.driverLocation)
            ride?.let { add(it.pickup); if (preview || dropoff) add(it.destination) }
            route?.let { addAll(it.points) }; pickupRoute?.let { addAll(it.points) }
        }
        runCatching {
            if (points.distinct().size > 1) {
                val bounds = LatLngBounds.Builder(); points.forEach(bounds::include)
                camera.animate(CameraUpdateFactory.newLatLngBounds(bounds.build(), 64), 420)
            } else camera.animate(CameraUpdateFactory.newLatLngZoom(state.driverLocation, 14f), 420)
        }
    }
    Box(Modifier.fillMaxSize()) {
        if (BuildConfig.MAPS_API_KEY_CONFIGURED) GoogleMap(
            modifier = Modifier.fillMaxSize(), cameraPositionState = camera,
            contentPadding = PaddingValues(top = topInset, bottom = bottomInset),
            properties = MapProperties(isMyLocationEnabled = false, mapStyleOptions = driverMapStyle()),
            uiSettings = MapUiSettings(zoomControlsEnabled = false, myLocationButtonEnabled = false, mapToolbarEnabled = false, scrollGesturesEnabled = true, zoomGesturesEnabled = true, rotationGesturesEnabled = true, tiltGesturesEnabled = true),
            onMapLoaded = { loaded = true }
        ) {
            Marker(state = rememberUpdatedMarkerState(smoothDriverLocation), title = "You",
                icon = BitmapDescriptorFactory.defaultMarker(BitmapDescriptorFactory.HUE_AZURE))
            ride?.let {
                Marker(state = rememberUpdatedMarkerState(it.pickup), title = "Pickup", snippet = it.pickupName,
                    icon = BitmapDescriptorFactory.defaultMarker(BitmapDescriptorFactory.HUE_GREEN))
                Marker(state = rememberUpdatedMarkerState(it.destination), title = "Drop-off", snippet = it.destinationName,
                    icon = BitmapDescriptorFactory.defaultMarker(BitmapDescriptorFactory.HUE_VIOLET))
            }
            pickupRoute?.let { Polyline(points = it.points, color = Color(0xFF2878FF), width = 10f) }
            route?.let { Polyline(points = it.points, color = Color(0xFF167A5B), width = 12f) }
        } else Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
            Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(Icons.Default.Map, null, Modifier.size(40.dp))
                Text("Map unavailable", fontWeight = FontWeight.Bold)
                Text("Map setup is required for this build.", style = MaterialTheme.typography.bodySmall)
            }
        }
        if (ride != null) Surface(Modifier.align(Alignment.TopStart).padding(10.dp), shape = RoundedCornerShape(12.dp)) {
            Row(Modifier.padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(when {
                    loading -> "Loading road route…"
                    routeFailed -> "Road route incomplete"
                    preview -> "Blue: to pickup · Green: trip"
                    dropoff -> "Route to drop-off"
                    else -> "Route to pickup"
                }, style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
                if (routeFailed && !loading) TextButton(onClick = { retry++ }) { Text("Retry") }
            }
        }
        FilledIconButton(onClick = { userMovedCamera = false; fit++ }, modifier = Modifier.align(Alignment.BottomEnd).padding(end = 16.dp, bottom = bottomInset + 14.dp).size(52.dp)) {
            Icon(Icons.Default.CenterFocusStrong, if (ride == null) "Recenter on your location" else "Show full route")
        }
    }
}

@Composable
private fun TodayStrip(state: DriverUiState) {
    Surface(shape = RoundedCornerShape(18.dp), shadowElevation = 2.dp) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 11.dp, horizontal = 14.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            MiniStat("Today", money(state.todayEarnings))
            MiniStat("Trips", state.todayTrips.toString())
            MiniStat("Session", "${state.onlineMinutes / 60}h ${state.onlineMinutes % 60}m")
        }
    }
}

@Composable
private fun MiniStat(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, fontWeight = FontWeight.Bold)
        Text(label, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun DedicatedRequestScreen(
    state: DriverUiState,
    ride: RideRequest,
    onAccept: () -> Unit,
    onDecline: () -> Unit
) {
    var now by remember(ride.id) { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(ride.id, ride.expiresAtEpochMs) {
        while (true) { now = System.currentTimeMillis(); delay(250) }
    }
    val active = ride.expiresAtEpochMs <= 0 || now < ride.expiresAtEpochMs
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val landscape=maxWidth>maxHeight && maxWidth>=600.dp
        val sheetLimit=if(landscape) maxHeight else maxHeight*.73f
        val details: @Composable () -> Unit = {
            Surface(shape=RoundedCornerShape(topStart=24.dp,topEnd=24.dp)) {
                Column(Modifier.fillMaxWidth().heightIn(max=sheetLimit)) {
                    Column(Modifier.weight(1f,fill=false).verticalScroll(rememberScrollState())) {
                        state.connectionError?.let { DriverNotice("Could not update request",it,true) }
                        RideRequestCard(ride,state.remoteMode,state.busy,onAccept,onDecline,showActions=false)
                    }
                    HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
                    Row(Modifier.fillMaxWidth().padding(16.dp),horizontalArrangement=Arrangement.spacedBy(12.dp)) {
                        OutlinedButton(onClick=onDecline,enabled=!state.busy && active,modifier=Modifier.weight(1f).heightIn(min=56.dp)) { Text("Decline") }
                        Button(onClick=onAccept,enabled=!state.busy && active,modifier=Modifier.weight(1.5f).heightIn(min=56.dp)) {
                            if(state.busy) { CircularProgressIndicator(Modifier.size(18.dp),strokeWidth=2.dp,color=MaterialTheme.colorScheme.onPrimary);Spacer(Modifier.width(8.dp)) }
                            Text(if(!active) "Expired" else if(state.busy) "Updating…" else if(ride.offerMode=="RADAR") "Match ride" else "Accept ride")
                        }
                    }
                }
            }
        }
        if(landscape) Row(Modifier.fillMaxSize()) {
            Box(Modifier.weight(1f).fillMaxHeight()) { DriverMap(state) }
            Box(Modifier.weight(1f).fillMaxHeight(),contentAlignment=Alignment.BottomCenter) { details() }
        } else Column(Modifier.fillMaxSize()) {
            Box(Modifier.fillMaxWidth().weight(1f)) { DriverMap(state) };details()
        }
    }
}


@Composable
private fun RideRequestCard(
    ride: RideRequest,
    remoteMode: Boolean,
    busy: Boolean,
    onAccept: () -> Unit,
    onDecline: () -> Unit,
    modifier: Modifier = Modifier,
    showActions: Boolean = true
) {
    var now by remember(ride.id) { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(ride.id, ride.expiresAtEpochMs) {
        while (ride.expiresAtEpochMs > 0L && now < ride.expiresAtEpochMs) {
            delay(250)
            now = System.currentTimeMillis()
        }
    }
    val secondsLeft = if (ride.expiresAtEpochMs > 0L)
        ((ride.expiresAtEpochMs - now + 999L) / 1000L).coerceAtLeast(0L) else 0L
    val offerActive = ride.expiresAtEpochMs <= 0L || secondsLeft > 0L
    val totalMinutes = ride.pickupEtaMin + ride.tripEtaMin
    val combinedKm = ride.pickupDistanceKm + ride.tripDistanceKm
    val grossPerHour = if (totalMinutes > 0) ride.driverEstimatedEarningsCad * 60.0 / totalMinutes else 0.0
    Surface(modifier = modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp),
        color = MaterialTheme.colorScheme.surface, shadowElevation = 0.dp) {
        Column(Modifier.padding(horizontal=20.dp,vertical=16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            if (ride.offerMode == "RADAR") {
                Surface(shape = RoundedCornerShape(12.dp), color = MaterialTheme.colorScheme.primaryContainer) {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 11.dp, vertical = 7.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Radar, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(7.dp))
                        Text("Trip Radar · shared with ${ride.nearbyDriverCount} nearby drivers",
                            style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                    }
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("ESTIMATED EARNINGS", color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.labelLarge)
                    Text(money(ride.driverEstimatedEarningsCad),
                        style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
                    Text("Test trip · gross before costs", style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(ride.category, fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleMedium)
                    Text(if (ride.pickupDistanceKm <= 0.1) "Driver near pickup"
                        else "${ride.pickupEtaMin} min to pickup", style = MaterialTheme.typography.bodySmall)
                }
            }
            if (remoteMode && ride.expiresAtEpochMs > 0L) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(if (offerActive) "${secondsLeft}s remaining" else "Request expired",
                        color = if (offerActive) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                        fontWeight = FontWeight.Bold)
                    Spacer(Modifier.weight(1f))
                    Text(if(ride.offerMode=="RADAR") "First available match" else "Exclusive offer", color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.labelSmall)
                }
                LinearProgressIndicator(progress = { (secondsLeft.toFloat() / 20f).coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().height(7.dp).clip(RoundedCornerShape(7.dp)))
            }
            HorizontalDivider()
            RouteLine(Icons.Default.RadioButtonChecked, ride.pickupName,
                if (ride.pickupDistanceKm <= 0.1) "Pickup · nearby" else
                    "Pickup · ${"%.1f".format(Locale.US,ride.pickupDistanceKm)} km · ${ride.pickupEtaMin} min")
            RouteLine(Icons.Default.LocationOn, ride.destinationName,
                "Destination · ${"%.1f".format(Locale.US,ride.tripDistanceKm)} km · ${ride.tripEtaMin} min")
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Column(Modifier.weight(1f)) {
                    Text("TOTAL TIME", style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("~${totalMinutes} min", fontWeight = FontWeight.SemiBold)
                }
                Column(Modifier.weight(1f)) {
                    Text("TOTAL DISTANCE", style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("~${"%.1f".format(Locale.US,combinedKm)} km", fontWeight = FontWeight.SemiBold)
                }
                Column(Modifier.weight(1f)) {
                    Text("GROSS / HOUR*", style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(if (totalMinutes > 0) "~${money(grossPerHour)}" else "N/A",
                        fontWeight = FontWeight.SemiBold)
                }
            }
            Text("*Gross estimate for this offer; not net profit or an hourly wage.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (showActions) Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = onDecline, enabled = !busy && offerActive,
                    modifier = Modifier.weight(1f).heightIn(min = 58.dp)) { Text("Decline") }
                Button(onClick = onAccept, enabled = !busy && offerActive,
                    modifier = Modifier.weight(2f).heightIn(min = 58.dp)) {
                    Text(if (!offerActive) "Expired" else if (ride.offerMode == "RADAR") "Match ride" else "Accept ride")
                }
            }
        }
    }
}

@Composable
private fun ActiveRideCard(
    state: DriverUiState,
    ride: RideRequest,
    onArrived: () -> Unit,
    onStartTrip: (String) -> Unit,
    onCompleteTrip: () -> Unit,
    onNavigate: (LatLng) -> Unit,
    onSafety: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier
) {
    var enteredPin by remember(ride.id) { mutableStateOf("") }
    val (title, destinationText) = when (state.rideStage) {
        RideStage.ACCEPTED, RideStage.ARRIVING -> "Heading to pickup" to ride.pickupName
        RideStage.ARRIVED -> "You have arrived" to ride.pickupName
        RideStage.ON_TRIP -> "Trip in progress" to ride.destinationName
        else -> "Active ride" to ride.destinationName
    }
    Column(modifier.fillMaxSize().imePadding()) {
        Column(Modifier.weight(1f, fill = true).verticalScroll(rememberScrollState()).padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(title,style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold,modifier=Modifier.semantics { liveRegion=LiveRegionMode.Polite })
            Text(destinationText, style = MaterialTheme.typography.bodyLarge)
            state.connectionError?.let { DriverNotice("Trip update failed", it, true) }
            if (state.resumedRide) DriverNotice("Trip restored", "Continue with your current trip.")
            LinearProgressIndicator(progress = { state.routeProgress.coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
            Text("${ride.rider.name} · ${ride.category}", color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (state.nextStopDistanceKm != null && state.nextStopEtaMin != null)
                Text("~${state.nextStopEtaMin} min · ${"%.1f".format(state.nextStopDistanceKm)} km to next stop", fontWeight = FontWeight.SemiBold)
            OutlinedButton(onClick = { onNavigate(if (state.rideStage == RideStage.ON_TRIP) ride.destination else ride.pickup) },
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                Icon(Icons.Default.Navigation, null); Spacer(Modifier.width(8.dp)); Text("Open navigation")
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onSafety, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Default.Shield, null); Spacer(Modifier.width(6.dp)); Text("Safety")
                }
                if (state.rideStage != RideStage.ON_TRIP) TextButton(onClick = onCancel, enabled = !state.busy,
                    modifier = Modifier.weight(1f)) { Text("Cancel trip", color = MaterialTheme.colorScheme.error) }
            }
        }
        Surface(shadowElevation = 6.dp) {
            Column(Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.rideStage == RideStage.ARRIVED) {
                    OutlinedTextField(enteredPin, { enteredPin = it.filter(Char::isDigit).take(4) },
                        label = { Text("Passenger PIN") }, modifier = Modifier.fillMaxWidth(), singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                        isError = state.pinError != null,
                        supportingText = { Text(state.pinError ?: if (state.remoteMode) "Ask the passenger for their 4-digit PIN" else "Demo PIN: 5824") })
                }
                Button(onClick = {
                    when (state.rideStage) {
                        RideStage.ACCEPTED, RideStage.ARRIVING -> onArrived()
                        RideStage.ARRIVED -> onStartTrip(enteredPin)
                        RideStage.ON_TRIP -> onCompleteTrip()
                        else -> Unit
                    }
                }, enabled = !state.busy && (state.rideStage != RideStage.ARRIVED || enteredPin.length == 4),
                    modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp)) {
                    Text(if (state.busy) "Updating…" else when (state.rideStage) {
                        RideStage.ACCEPTED, RideStage.ARRIVING -> "I've arrived"
                        RideStage.ARRIVED -> "Verify PIN & start trip"
                        RideStage.ON_TRIP -> "Complete trip"
                        else -> "Continue"
                    })
                }
            }
        }
    }
}

private fun openNavigation(context: Context, destination: LatLng) {
    val uri = Uri.Builder().scheme("https").authority("www.google.com").path("/maps/dir/")
        .appendQueryParameter("api", "1")
        .appendQueryParameter("destination", "${destination.latitude},${destination.longitude}")
        .appendQueryParameter("travelmode", "driving").build()
    runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, uri)) }
        .onFailure { Toast.makeText(context, "No map or browser app is available", Toast.LENGTH_LONG).show() }
}

private fun shareTrip(context: Context, ride: RideRequest, lastDeviceLocation: LatLng?, remoteMode: Boolean) {
    val location = lastDeviceLocation?.let {
        "\nLast device position: https://www.google.com/maps/search/?api=1&query=${it.latitude}%2C${it.longitude}"
    }.orEmpty()
    val message = "RideNova ${if (remoteMode) "local test" else "demo"} trip ${ride.id}\nPickup: ${ride.pickupName}\n" +
        "Destination: ${ride.destinationName}$location\nThis is a one-time share, not live tracking."
    val send = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, message)
    }
    runCatching { context.startActivity(Intent.createChooser(send, "Share trip details")) }
        .onFailure { Toast.makeText(context, "No share app is available", Toast.LENGTH_LONG).show() }
}

@Composable
private fun CompletedRideCard(ride: RideRequest, remoteMode: Boolean, onDone: () -> Unit, modifier: Modifier = Modifier) {
    Surface(modifier = modifier.fillMaxWidth().padding(12.dp), shape = RoundedCornerShape(28.dp), shadowElevation = 12.dp) {
        Column(Modifier.padding(22.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Icon(Icons.Default.CheckCircle, null, Modifier.size(52.dp), tint = Color(0xFF209454))
            Text(if(remoteMode) "Trip complete" else "Demo trip complete", fontWeight = FontWeight.Bold, fontSize = 22.sp)
            Text("Estimated driver earnings")
            Text(money(ride.driverEstimatedEarningsCad), fontSize = 34.sp, fontWeight = FontWeight.Bold)
            Text("Trip fare ${money(ride.fareCad)} · no real payout")
            if (remoteMode) DriverExperienceActions(ride.id)
            Button(onClick=onDone,modifier=Modifier.fillMaxWidth().heightIn(min=52.dp)) { Text("Back to driver home") }
        }
    }
}

@Composable
private fun RouteLine(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String, supporting: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, Modifier.size(22.dp))
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(text, fontWeight = FontWeight.Medium)
            Text(supporting, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun EarningsScreen(state: DriverUiState,trips: List<CompletedTrip>,onTrip: (CompletedTrip)->Unit) {
    // Purely a display filter: no fabricated payouts, and no extra backend polling.
    var period by rememberSaveable { mutableStateOf("Today") }
    val today = java.time.LocalDate.now()
    val weekStart = today.with(java.time.DayOfWeek.MONDAY)
    val filteredTrips = remember(trips, period, today) {
        trips.filter { trip ->
            val date = java.time.Instant.ofEpochMilli(trip.completedAtEpochMs)
                .atZone(java.time.ZoneId.systemDefault()).toLocalDate()
            when (period) {
                "Today" -> date == today
                "This week" -> date >= weekStart && date <= today
                else -> true
            }
        }
    }
    val estimatedEarnings = filteredTrips.sumOf(CompletedTrip::driverEarningsCad)
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Spacer(Modifier.height(12.dp))
        NovaSection("Your earnings","Track your trips. Test amounts are not a payout balance.")
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            listOf("Today", "This week", "All time").forEach { option ->
                FilterChip(selected = period == option, onClick = { period = option },
                    label = { Text(option) })
            }
        }
        Surface(Modifier.fillMaxWidth(),shape=RoundedCornerShape(24.dp),color=MaterialTheme.colorScheme.primaryContainer) { Column(Modifier.padding(24.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) { Text(period.uppercase()+" · ESTIMATED GROSS",style=MaterialTheme.typography.labelMedium);Text(money(estimatedEarnings),style=MaterialTheme.typography.displayMedium);Text("CAD · before costs",style=MaterialTheme.typography.bodySmall) } }
        Surface(shape = RoundedCornerShape(22.dp), tonalElevation = 2.dp) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                EarningsRow("Completed trips", filteredTrips.size.toString())
                EarningsRow("Average estimated earnings per trip",
                    money(if (filteredTrips.isEmpty()) 0.0 else estimatedEarnings / filteredTrips.size))
                if (period == "Today") {
                    EarningsRow("Online this session", "${state.onlineMinutes / 60}h ${state.onlineMinutes % 60}m")
                }
                HorizontalDivider()
                Text("Amounts reflect trip estimates before personal costs and tax settlement. No real payouts or card charges occur in development.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
            }
        }
        if (filteredTrips.isEmpty()) {
            DriverNotice("No completed trips for $period", "Choose another period or complete a ride to see its estimated earnings here.")
        } else {
            Text("Recent trips · $period", fontWeight = FontWeight.Bold, fontSize = 20.sp)
            filteredTrips.sortedByDescending { it.completedAtEpochMs }.take(5).forEach { trip ->
                Surface(onClick={onTrip(trip)},shape=RoundedCornerShape(18.dp),tonalElevation=1.dp) {
                    Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        EarningsRow(trip.completedAt, money(trip.driverEarningsCad))
                        Text("${trip.pickup} → ${trip.destination}", maxLines = 2, overflow = TextOverflow.Ellipsis,
                            color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                        Text("${trip.distanceKm} km · ${trip.durationMin} min · passenger fare ${money(trip.grossFareCad)}",
                            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun EarningsRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, Modifier.weight(1f))
        Spacer(Modifier.width(12.dp))
        Text(value, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun TripHistoryScreen(trips: List<CompletedTrip>, onHome: () -> Unit, onTrip: (CompletedTrip) -> Unit) {
    var search by rememberSaveable { mutableStateOf("") }
    val shown=trips.filter { search.isBlank() || "${it.pickup} ${it.destination} ${it.id}".contains(search.trim(),ignoreCase=true) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Spacer(Modifier.height(12.dp))
        NovaSection("Trip history","Open a trip for its route, earnings and support.")
        Spacer(Modifier.height(14.dp))
        OutlinedTextField(search,{search=it},Modifier.fillMaxWidth(),singleLine=true,label={Text("Search trips")},placeholder={Text("Address or trip ID")},leadingIcon={Icon(Icons.Default.Search,null)},trailingIcon={if(search.isNotEmpty()) IconButton(onClick={search=""}) { Icon(Icons.Default.Close,"Clear trip search") }})
        Spacer(Modifier.height(14.dp))
        if(shown.isEmpty() && trips.isNotEmpty()) NovaNotice("No matching trips","Try a pickup address, destination or trip ID.")
        if (trips.isEmpty()) {
            Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Icon(Icons.Default.Route, null, Modifier.size(52.dp), tint = MaterialTheme.colorScheme.secondary)
                    Text("Your first trip starts here", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text("Completed trips will appear here with the route, date and estimated earnings.")
                    Button(onClick = onHome, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text("Go to driver home") }
                }
            }
        }
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            shown.sortedByDescending { it.completedAtEpochMs }.forEach { trip ->
                Surface(shape = RoundedCornerShape(20.dp), tonalElevation = 2.dp,
                    modifier = Modifier.fillMaxWidth().clickable { onTrip(trip) }) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(trip.completedAt, fontWeight = FontWeight.SemiBold)
                            Text(money(trip.driverEarningsCad), fontWeight = FontWeight.Bold)
                        }
                        Text("${trip.pickup} → ${trip.destination}", maxLines = 2, overflow = TextOverflow.Ellipsis)
                        Text("${trip.distanceKm} km · ${trip.durationMin} min · fare ${money(trip.grossFareCad)}", fontSize = 12.sp)
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                            Text("View route and details", color = MaterialTheme.colorScheme.primary,
                                style = MaterialTheme.typography.labelLarge)
                            Icon(Icons.Default.ChevronRight, null, Modifier.size(20.dp), tint = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
        }
    }
}

@Composable
private fun DriverTripDetailScreen(trip: CompletedTrip, onBack: () -> Unit) {
    val points = trip.routePoints.ifEmpty { listOfNotNull(trip.pickupPoint, trip.destinationPoint) }
    val camera = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(points.firstOrNull() ?: LatLng(49.2827, -123.1207), 12f)
    }
    LaunchedEffect(trip.id, points) {
        if (points.size >= 2) {
            val bounds = LatLngBounds.builder().apply { points.forEach { include(it) } }.build()
            runCatching { camera.animate(CameraUpdateFactory.newLatLngBounds(bounds, 90)) }
        }
    }
    Column(Modifier.fillMaxSize()) {
        Box(Modifier.fillMaxWidth().weight(.52f)) {
            if (points.isNotEmpty() && BuildConfig.MAPS_API_KEY_CONFIGURED) {
                GoogleMap(Modifier.fillMaxSize(), cameraPositionState = camera,
                    uiSettings = MapUiSettings(zoomControlsEnabled = false, compassEnabled = true)) {
                    trip.pickupPoint?.let { Marker(rememberUpdatedMarkerState(it), title = trip.pickup) }
                    trip.destinationPoint?.let { Marker(rememberUpdatedMarkerState(it), title = trip.destination) }
                    if (points.size > 1) Polyline(points, color = MaterialTheme.colorScheme.primary, width = 11f)
                }
            } else Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
                Text("Route map unavailable", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            FilledIconButton(onClick = onBack, modifier = Modifier.statusBarsPadding().padding(14.dp)) {
                Icon(Icons.Default.ArrowBack, "Back to trips")
            }
        }
        Column(Modifier.fillMaxWidth().weight(.48f).verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Trip details", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(trip.completedAt, color = MaterialTheme.colorScheme.onSurfaceVariant)
            RouteLine(Icons.Default.RadioButtonChecked, trip.pickup, "Pickup address")
            RouteLine(Icons.Default.LocationOn, trip.destination, "Destination")
            HorizontalDivider()
            EarningsRow("Ride type", trip.category.ifBlank { "RideNova" })
            EarningsRow("Distance", "${trip.distanceKm} km")
            EarningsRow("Time", "${trip.durationMin} min")
            EarningsRow("Passenger fare", money(trip.grossFareCad))
            EarningsRow("Your estimated earnings", money(trip.driverEarningsCad))
            DriverExperienceActions(trip.id)
        }
    }
}

@Composable
private fun DriverExperienceActions(rideId: String) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var ratingOpen by remember { mutableStateOf(false) }
    var supportOpen by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var confirmation by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val token = remember { com.ridenova.driver.data.FleetCredentials(context).load() }
    val api = remember(token) { com.ridenova.driver.data.DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL, token, true) }
    if (token.isBlank()) return
    Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { ratingOpen = true }, enabled = !busy, modifier = Modifier.weight(1f)) {
                Icon(Icons.Default.Star, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Rate rider")
            }
            OutlinedButton(onClick = { supportOpen = true }, enabled = !busy, modifier = Modifier.weight(1f)) {
                Icon(Icons.Default.Shield, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Support")
            }
        }
        confirmation?.let { Text(it, color = Color(0xFF209454), fontSize = 12.sp) }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp) }
    }
    if (ratingOpen) DriverRatingDialog(busy=busy,error=error,onDismiss = { ratingOpen = false }) { stars, tags, comment ->
        scope.launch {
            busy = true; error = null
            runCatching {
                api.json("POST", "v2/fleet/driver/rides/$rideId/rating", org.json.JSONObject()
                    .put("stars", stars).put("tags", org.json.JSONArray(tags)).put("comment", comment))
            }.onSuccess { confirmation = "Rider rating saved"; ratingOpen = false }
                .onFailure { error = it.localizedMessage ?: "Could not save rating" }
            busy = false
        }
    }
    if (supportOpen) DriverSupportDialog(busy=busy,error=error,onDismiss = { supportOpen = false }) { category, description ->
        scope.launch {
            busy = true; error = null
            runCatching {
                api.json("POST", "v2/fleet/driver/support-cases", org.json.JSONObject()
                    .put("rideId", rideId).put("category", category).put("description", description))
            }.onSuccess { confirmation = "Support case created"; supportOpen = false }
                .onFailure { error = it.localizedMessage ?: "Could not create support case" }
            busy = false
        }
    }
}

@Composable
private fun DriverRatingDialog(busy: Boolean=false,error: String?=null,onDismiss: () -> Unit, onSubmit: (Int, List<String>, String) -> Unit) {
    var stars by remember { mutableStateOf(5) }
    var comment by remember { mutableStateOf("") }
    var selected by remember { mutableStateOf(setOf<String>()) }
    val tags = listOf("RESPECTFUL" to "Respectful", "CLEAR_COMMUNICATION" to "Clear communication", "EASY_PICKUP" to "Easy pickup")
    AlertDialog(onDismissRequest={if(!busy)onDismiss()}, title = { Text("Rate your rider") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()).imePadding(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
                (1..5).forEach { value -> IconButton(onClick = { stars = value }) {
                    Icon(if (value <= stars) Icons.Default.Star else Icons.Default.StarBorder, "$value stars", tint = Color(0xFFFFB000))
                } }
            }
            tags.forEach { (key, label) -> FilterChip(selected = key in selected, onClick = {
                selected = if (key in selected) selected - key else selected + key
            }, label = { Text(label) }, leadingIcon = if (key in selected) {{ Icon(Icons.Default.Check, null) }} else null) }
            OutlinedTextField(comment, { comment = it.take(500) }, Modifier.fillMaxWidth(), label = { Text("Private feedback (optional)") }, minLines = 3)
            error?.let { Text(it,color=MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = { Button(enabled=!busy,onClick = { onSubmit(stars, selected.toList(), comment.trim()) }) { Text(if(busy) "Saving…" else "Save rating") } },
        dismissButton = { TextButton(onClick=onDismiss,enabled=!busy) { Text("Cancel") } })
}

@Composable
private fun DriverSupportDialog(busy: Boolean=false,error: String?=null,onDismiss: () -> Unit, onSubmit: (String, String) -> Unit) {
    var category by remember { mutableStateOf("PASSENGER") }
    var description by remember { mutableStateOf("") }
    AlertDialog(onDismissRequest={if(!busy)onDismiss()}, title = { Text("Trip support") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()).imePadding(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            listOf("PASSENGER" to "Passenger concern", "SAFETY" to "Safety", "FARE" to "Fare or earnings", "APP" to "App issue", "OTHER" to "Other").forEach { (key, label) ->
                FilterChip(selected = category == key, onClick = { category = key }, label = { Text(label) })
            }
            OutlinedTextField(description, { description = it.take(1000) }, Modifier.fillMaxWidth(), label = { Text("Describe the issue") }, minLines = 4,
                supportingText = { Text("${description.trim().length}/1000 · at least 10 characters") })
            error?.let { Text(it,color=MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = { Button(enabled=!busy && description.trim().length>=10, onClick = { onSubmit(category, description.trim()) }) { Text(if(busy) "Sending…" else "Submit case") } },
        dismissButton = { TextButton(onClick=onDismiss,enabled=!busy) { Text("Cancel") } })
}

@Composable
private fun AccountScreen(profile: DriverProfile, tripCount: Int, onSave: (String, String, String) -> Unit,
    fleet: Boolean, onDocuments: () -> Unit, onAccess: () -> Unit) {
    val context = LocalContext.current
    var editing by remember { mutableStateOf(false) }
    var selectedSection by remember { mutableStateOf("") }
    var name by remember(profile.name) { mutableStateOf(profile.name) }
    var vehicle by remember(profile.vehicle) { mutableStateOf(profile.vehicle) }
    var plate by remember(profile.plate) { mutableStateOf(profile.plate) }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(7.dp)
    ) {
        Spacer(Modifier.height(8.dp))
        Surface(shape = CircleShape, color = MaterialTheme.colorScheme.surfaceVariant, modifier = Modifier.size(72.dp)) {
            Box(contentAlignment = Alignment.Center) { Icon(Icons.Default.Person, null, Modifier.size(38.dp)) }
        }
        Text(profile.name, fontSize = 25.sp, fontWeight = FontWeight.Bold)
        Text("$tripCount completed trips · driver account", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(12.dp))
        Text("YOUR ACCOUNT", modifier = Modifier.fillMaxWidth(), fontWeight = FontWeight.Bold)
        AccountRow(Icons.Default.Person, "Profile and vehicle", "Name, car and licence plate") { editing = true }
        AccountRow(Icons.Default.Description, "Documents & onboarding", "Uploads, expiry dates and review status") {
            if (fleet) onDocuments() else selectedSection = "Documents"
        }
        if (fleet) AccountRow(Icons.Default.Logout, "Sign-in & logout", "Switch driver accounts on this phone", onAccess)
        AccountRow(Icons.Default.ReceiptLong, "Tax information", "GST and tax setup guidance · no sensitive entry") { selectedSection = "Tax information" }
        Spacer(Modifier.height(12.dp))
        Text("DRIVING & SUPPORT", modifier = Modifier.fillMaxWidth(), fontWeight = FontWeight.Bold)
        AccountRow(Icons.Default.Settings, "Settings", "Permissions, navigation and notification controls") { selectedSection = "Settings" }
        AccountRow(Icons.Default.Shield, "Safety and support", "Help, incident reporting and emergency guidance") { selectedSection = "Safety and support" }
        AccountRow(Icons.Default.Info, "About RideNova", "Version ${BuildConfig.VERSION_NAME} · development") { selectedSection = "About RideNova" }
        Spacer(Modifier.height(12.dp))
        Text("Document review is available for signed-in fleet drivers. Tax verification and real payouts are not connected.",
            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    if (editing) {
        AlertDialog(
            onDismissRequest = { editing = false },
            title = { Text("Driver and vehicle profile") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(name, { name = it.take(60) }, label = { Text("Your name") }, singleLine = true)
                    OutlinedTextField(vehicle, { vehicle = it.take(80) }, label = { Text("Vehicle") }, singleLine = true)
                    OutlinedTextField(plate, { plate = it.take(16) }, label = { Text("Licence plate") }, singleLine = true)
                    Text("Development profile only; changes do not verify driver eligibility.", fontSize = 12.sp)
                }
            },
            confirmButton = { TextButton(onClick = { onSave(name, vehicle, plate); editing = false },
                enabled = name.isNotBlank() && vehicle.isNotBlank() && plate.isNotBlank()) { Text("Save") } },
            dismissButton = { TextButton(onClick = { editing = false }) { Text("Cancel") } }
        )
    }
    if (selectedSection.isNotEmpty()) {
        AlertDialog(
            onDismissRequest = { selectedSection = "" },
            title = { Text(selectedSection) },
            text = { Text(when (selectedSection) {
                "Documents" -> "Driver licence, vehicle registration, commercial insurance, and inspection records will have individual upload, expiry and approval states in a future authenticated onboarding release. This screen is a checklist preview; no document is uploaded or verified."
                "Tax information" -> "This development version shows illustrative fares and earnings only. Tax registration, secure tax-information collection, statements and payment reporting must be implemented with appropriate verification before launch. Do not enter personal tax identifiers here."
                "Settings" -> "To adjust RideNova location and notification permissions, open Android app settings. Navigation currently provides an in-app beta with a Google Maps fallback."
                "Safety and support" -> "During a real emergency, contact local emergency services. Trip-linked support cases are available after completed rides; real-time emergency response and secure messaging are not connected."
                else -> "RideNova Driver ${BuildConfig.VERSION_NAME}. Passenger, Driver and Admin use one shared backend for post-trip ratings, private feedback and support-case review. Development-only features still do not verify identities or process real payments."
            }) },
            confirmButton = {
                if (selectedSection == "Settings") {
                    TextButton(onClick = {
                        val intent = Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                            Uri.parse("package:${context.packageName}"))
                        context.startActivity(intent)
                        selectedSection = ""
                    }) { Text("Android app settings") }
                } else TextButton(onClick = { selectedSection = "" }) { Text("OK") }
            },
            dismissButton = { if (selectedSection == "Settings") TextButton(onClick = { selectedSection = "" }) { Text("Close") } }
        )
    }
}

@Composable
private fun AccountRow(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, subtitle: String,
                       onClick: () -> Unit) {
    Surface(shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp)
        .clickable(onClick = onClick), tonalElevation = 1.dp) {
        Row(Modifier.padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold)
                Text(subtitle, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(Icons.Default.ChevronRight, null)
        }
    }
}

@Composable
private fun rememberSmoothLatLng(target: LatLng): LatLng {
    val latitude by animateFloatAsState(
        targetValue = target.latitude.toFloat(),
        animationSpec = tween(durationMillis = 900, easing = FastOutSlowInEasing),
        label = "driver-marker-latitude"
    )
    val longitude by animateFloatAsState(
        targetValue = target.longitude.toFloat(),
        animationSpec = tween(durationMillis = 900, easing = FastOutSlowInEasing),
        label = "driver-marker-longitude"
    )
    return LatLng(latitude.toDouble(), longitude.toDouble())
}

private fun money(value: Double): String = NumberFormat.getCurrencyInstance(Locale.CANADA).format(value)


/** In-app BETA road-route experience. Not a certified navigation SDK: no spoken or lane guidance. */
@Composable
private fun DriverNavigationScreen(state: DriverUiState, onExit: () -> Unit, onOpenGoogleMaps: () -> Unit) {
    val context = LocalContext.current
    val ride = state.activeRide ?: return
    val destination = if (state.rideStage == RideStage.ON_TRIP) ride.destination else ride.pickup
    val destinationName = if (state.rideStage == RideStage.ON_TRIP) ride.destinationName else ride.pickupName
    val camera = rememberCameraPositionState { position = CameraPosition.fromLatLngZoom(state.driverLocation, 16f) }
    var route by remember(ride.id, state.rideStage == RideStage.ON_TRIP) { mutableStateOf<RoadRoute?>(null) }
    var error by remember(ride.id, state.rideStage == RideStage.ON_TRIP) { mutableStateOf<String?>(null) }
    var loading by remember(ride.id, state.rideStage == RideStage.ON_TRIP) { mutableStateOf(true) }
    var follow by remember { mutableStateOf(true) }
    val latestLocation by rememberUpdatedState(state.driverLocation)
    val smoothDriverLocation = rememberSmoothLatLng(state.driverLocation)
    LaunchedEffect(camera) {
        snapshotFlow { camera.cameraMoveStartedReason }.collect { reason ->
            if (reason == CameraMoveStartedReason.GESTURE) follow = false
        }
    }
    // Refresh route every 30 seconds from the CURRENT driver position, not the first composition.
    LaunchedEffect(ride.id, destination) {
        while (true) {
            loading = route == null
            DriverRoadRoutes.fetch(context, latestLocation, destination).fold(
                onSuccess = { route = it; error = null },
                onFailure = { error = it.message ?: "Routes unavailable" }
            )
            loading = false
            delay(30_000)
        }
    }
    LaunchedEffect(state.driverLocation, follow) {
        if (follow) runCatching { camera.animate(CameraUpdateFactory.newLatLngZoom(state.driverLocation, 16.5f), 550) }
    }
    val step = route?.steps?.firstOrNull { s ->
        val result = FloatArray(1)
        Location.distanceBetween(state.driverLocation.latitude, state.driverLocation.longitude, s.end.latitude, s.end.longitude, result)
        result[0] > 35f
    } ?: route?.steps?.lastOrNull()
    val mapContent: @Composable () -> Unit = {
        GoogleMap(
            modifier = Modifier.fillMaxSize(), cameraPositionState = camera,
            properties = MapProperties(isMyLocationEnabled = false, mapStyleOptions = driverMapStyle()),
            uiSettings = MapUiSettings(zoomControlsEnabled = false, mapToolbarEnabled = false, compassEnabled = true),
            onMapClick = { follow = false }
        ) {
            Marker(state = rememberUpdatedMarkerState(smoothDriverLocation), title = "Driver position")
            Marker(state = rememberUpdatedMarkerState(destination), title = destinationName)
            route?.let { if (it.points.size > 1) Polyline(points = it.points, color = Color(0xFF167A5B), width = 15f) }
        }
    }
    val controls: @Composable () -> Unit = {
        Column(Modifier.fillMaxSize()) {
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(18.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(if (state.rideStage == RideStage.ON_TRIP) "TO DROP-OFF" else "TO PICKUP",
                    style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.secondary)
                Text(if (loading) "Finding road route…" else step?.instruction ?: "Route unavailable",
                    style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text(destinationName)
                error?.let { DriverNotice("Route update unavailable", "Try Google Maps, or wait for the next update.", true) }
                Text(route?.let { "${it.etaMinutes} min · ${"%.1f".format(it.distanceMeters / 1000.0)} km" } ?: "ETA unavailable",
                    style = MaterialTheme.typography.titleMedium)
                Text("Visual route beta · follow road signs. No voice or lane guidance.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { follow = true }, modifier = Modifier.weight(1f)) { Text("Follow GPS") }
                    Button(onClick = onOpenGoogleMaps, modifier = Modifier.weight(1f)) { Text("Google Maps") }
                }
            }
            OutlinedButton(onClick = onExit, modifier = Modifier.fillMaxWidth().padding(12.dp).heightIn(min = 52.dp)) {
                Text("Return to trip")
            }
        }
    }
    BoxWithConstraints(Modifier.fillMaxSize()) {
        if (maxWidth > maxHeight && maxWidth >= 600.dp) Row(Modifier.fillMaxSize()) {
            Box(Modifier.weight(1f).fillMaxHeight()) { mapContent() }
            Surface(Modifier.weight(1f).fillMaxHeight()) { controls() }
        } else Column(Modifier.fillMaxSize()) {
            Box(Modifier.fillMaxWidth().weight(0.45f)) { mapContent() }
            Surface(Modifier.fillMaxWidth().weight(0.55f)) { controls() }
        }
    }
}

@Composable
private fun driverMapStyle(): MapStyleOptions? = if (MaterialTheme.colorScheme.background.luminance() < 0.3f)
    MapStyleOptions("""[
      {"elementType":"geometry","stylers":[{"color":"#182027"}]},
      {"elementType":"labels.text.fill","stylers":[{"color":"#bac5ce"}]},
      {"elementType":"labels.text.stroke","stylers":[{"color":"#182027"}]},
      {"featureType":"road","elementType":"geometry","stylers":[{"color":"#374450"}]},
      {"featureType":"water","elementType":"geometry","stylers":[{"color":"#0d1821"}]},
      {"featureType":"poi","elementType":"labels","stylers":[{"visibility":"off"}]}
    ]""") else null

// Android Studio previews of real app components, not rendered test evidence.
@androidx.compose.ui.tooling.preview.Preview(name = "Empty Trips · dark", widthDp = 360, heightDp = 640, uiMode = 32)
@androidx.compose.ui.tooling.preview.Preview(name = "Empty Trips · large text", widthDp = 360, heightDp = 640, fontScale = 1.5f, uiMode = 32)
@Composable
private fun EmptyTripsPreview() {
    com.ridenova.driver.ui.theme.RideNovaDriverTheme {
        Surface { TripHistoryScreen(emptyList(), {}, {}) }
    }
}

@androidx.compose.ui.tooling.preview.Preview(name = "Earnings · empty", widthDp = 360, heightDp = 640, uiMode = 32)
@Composable
private fun EmptyEarningsPreview() {
    com.ridenova.driver.ui.theme.RideNovaDriverTheme {
        Surface { EarningsScreen(DriverUiState(), emptyList(), {}) }
    }
}

@Composable
private fun DriverIdleHome(state: DriverUiState, onToggle: () -> Unit, onDemo: () -> Unit,
    onMenu: () -> Unit, onEarnings: () -> Unit, onAlerts: () -> Unit) {
    val density = LocalDensity.current
    var dockHeight by remember { mutableStateOf(200.dp) }
    val online = state.availability == DriverAvailability.ONLINE
    val title = when {
        state.busy -> "Updating your status…"
        state.remoteMode && state.connectionError != null -> "Connection needs attention"
        state.remoteMode && state.lastServerSyncMs == 0L -> "Checking driver status…"
        !online -> "You're offline"
        state.dispatchReason == "LOCATION_REQUIRED" || state.dispatchReason == "LOCATION_STALE" -> "Online · waiting for GPS"
        else -> "You're online"
    }
    val detail = when {
        state.connectionError != null -> state.connectionError
        !online -> "Go online when you're ready to receive rides."
        !state.locationPermissionGranted -> "Enable location permission to receive nearby requests."
        state.dispatchReason == "LOCATION_REQUIRED" -> "Waiting for your first location update."
        state.dispatchReason == "LOCATION_STALE" -> "Your location is out of date. Waiting for a fresh GPS fix."
        state.dispatchReason == "APPROVAL_REQUIRED" -> "Your driver account is awaiting approval. Open Account → Documents & onboarding for details."
        state.dispatchReason == "DOCUMENTS_REQUIRED" -> "One or more required documents are missing, rejected or expired. Open Account → Documents & onboarding."
        state.remoteMode -> "Listening for ${state.category.lowercase().ifBlank { "nearby" }} requests."
        else -> "Demo mode · sample requests only."
    }
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val dockLimit = maxHeight * 0.48f
        DriverMap(state, bottomInset = dockHeight, topInset = 82.dp)
        Row(Modifier.align(Alignment.TopCenter).fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(onClick = onMenu, modifier = Modifier.size(52.dp), shape = RoundedCornerShape(16.dp), shadowElevation = 5.dp) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Icon(Icons.Default.Menu, "Open driver menu") }
            }
            Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
                Surface(onClick = onEarnings, shape = RoundedCornerShape(24.dp), shadowElevation = 6.dp) {
                    Column(Modifier.padding(horizontal = 20.dp, vertical = 8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(money(state.todayEarnings), fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
                        Text("TODAY", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            Surface(onClick = onAlerts, modifier = Modifier.size(52.dp), shape = RoundedCornerShape(16.dp), shadowElevation = 5.dp) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Icon(Icons.Default.Notifications, "Request alerts and floating shortcut") }
            }
        }
        Surface(Modifier.align(Alignment.BottomCenter).fillMaxWidth().onSizeChanged { dockHeight = with(density) { it.height.toDp() } },
            shape = RoundedCornerShape(topStart = 26.dp, topEnd = 26.dp), shadowElevation = 8.dp) {
            Column {
                Column(Modifier.fillMaxWidth().heightIn(max = dockLimit).verticalScroll(rememberScrollState()).padding(start = 20.dp, end = 20.dp, top = 18.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)) { Icon(if(online) Icons.Default.RadioButtonChecked else Icons.Default.RadioButtonUnchecked,null,Modifier.size(16.dp),tint=MaterialTheme.colorScheme.primary);Text(if(online) "DRIVER AVAILABILITY · ONLINE" else "DRIVER AVAILABILITY · OFFLINE",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant) }
                    Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text(detail.orEmpty(), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                    Text("${state.todayTrips} trips today · ${state.onlineMinutes / 60}h ${state.onlineMinutes % 60}m online",
                        style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (!state.remoteMode && online) TextButton(onClick = onDemo) { Text("Try a demo request") }
                }
                Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(onClick = onToggle, enabled = !state.busy, modifier = Modifier.weight(1f).heightIn(min = 60.dp), shape = RoundedCornerShape(30.dp)) {
                        Icon(Icons.Default.PowerSettingsNew, null); Spacer(Modifier.width(10.dp))
                        Text(if (state.busy) "Updating…" else if (online) "Go offline" else "Go online", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    }
                    OutlinedIconButton(onClick = onAlerts, modifier = Modifier.size(60.dp)) { Icon(Icons.Default.Tune, "Driver alert settings") }
                }
            }
        }
    }
}
