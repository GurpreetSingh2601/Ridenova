@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
package com.ridenova.passenger.ui

import android.Manifest
import android.content.pm.PackageManager
import android.location.Geocoder
import android.os.SystemClock
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.*
import com.ridenova.passenger.model.BookingDraft
import com.ridenova.passenger.model.PlaceSuggestion
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

/** Pickup is a deliberate selection. Camera movements never update the booking directly. */
@Composable
internal fun PickupEditor43(
    draft: BookingDraft, searchResult: PlaceSuggestion?, onSearch: () -> Unit,
    onBack: () -> Unit, onConfirm: (PlaceSuggestion, Boolean, String) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var latitude by rememberSaveable { mutableStateOf(draft.pickup.latitude) }
    var longitude by rememberSaveable { mutableStateOf(draft.pickup.longitude) }
    var address by rememberSaveable { mutableStateOf(draft.pickup.address) }
    var name by rememberSaveable { mutableStateOf(draft.pickup.name) }
    var manual by rememberSaveable { mutableStateOf(draft.pickupManual) }
    var notes by rememberSaveable { mutableStateOf(draft.pickupNotes) }
    var issue by rememberSaveable { mutableStateOf<String?>(null) }
    var locating by remember { mutableStateOf(false) }
    var generation by remember { mutableIntStateOf(0) }
    var loaded by remember { mutableStateOf(false) }
    var consumedSearch by rememberSaveable { mutableStateOf<String?>(null) }
    var moveTo by remember { mutableStateOf<LatLng?>(null) }
    val camera = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(LatLng(latitude ?: 49.2827, longitude ?: -123.1207), 16f)
    }
    fun select(point: LatLng, isManual: Boolean) {
        val request = ++generation
        locating = false
        latitude = point.latitude; longitude = point.longitude; manual = isManual
        name = "Selected pickup"
        address = String.format(Locale.US, "Selected pin: %.5f, %.5f", point.latitude, point.longitude)
        issue = "Check that the pin marks a safe, accessible pickup point."
        scope.launch {
            @Suppress("DEPRECATION")
            val resolved = withContext(Dispatchers.IO) {
                runCatching { Geocoder(context, Locale.getDefault()).getFromLocation(point.latitude, point.longitude, 1)?.firstOrNull()?.getAddressLine(0) }.getOrNull()
            }
            if (request == generation) {
                if (!resolved.isNullOrBlank()) { address = resolved; name = resolved; issue = null }
                else issue = "Street address unavailable. Your driver will receive the selected coordinates and your pickup instructions."
            }
        }
    }
    fun locate() {
        val request = ++generation
        locating = true; issue = null
        scope.launch { delay(15_000); if (request == generation && locating) { generation++; locating = false; issue = "Location timed out. Search an address or select a point on the map." } }
        try {
            LocationServices.getFusedLocationProviderClient(context).getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, null)
                .addOnSuccessListener { location ->
                    if (request != generation) return@addOnSuccessListener
                    locating = false
                    if (location == null) issue = "GPS is unavailable. Search an address or choose a point on the map."
                    else if (!location.hasAccuracy() || location.accuracy > 100f ||
                        SystemClock.elapsedRealtimeNanos() - location.elapsedRealtimeNanos !in 0..60_000_000_000L) {
                        issue = "Your location is not accurate enough. Search or choose the pickup pin yourself."
                    } else { val point = LatLng(location.latitude, location.longitude); select(point, false); moveTo = point }
                }.addOnFailureListener {
                    if (request == generation) { locating = false; issue = "Could not get GPS. You can still search or select a pickup on the map." }
                }
        } catch (_: SecurityException) { locating = false; issue = "Location permission is off. Search or choose a pickup on the map." }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { granted ->
        if (granted.values.any { it }) locate()
        else issue = "Location permission is off. You can still book using an address or map pin."
    }
    LaunchedEffect(searchResult) {
        searchResult?.let { place ->
            val identity = "${place.latitude},${place.longitude}:${place.address}"
            if (identity == consumedSearch) return@let
            consumedSearch = identity
            if (place.latitude != null && place.longitude != null) {
                generation++; locating = false
                latitude = place.latitude; longitude = place.longitude
                address = place.address; name = place.name; manual = true; issue = null
                moveTo = LatLng(place.latitude, place.longitude)
            } else issue = "This address has no coordinates. Choose another result or select a map pin."
        }
    }
    LaunchedEffect(loaded, moveTo) { if (loaded) moveTo?.let { camera.move(CameraUpdateFactory.newLatLngZoom(it, 17f)); moveTo = null } }
    LaunchedEffect(camera) {
        snapshotFlow { camera.isMoving to camera.cameraMoveStartedReason }.collect { (moving, reason) ->
            if (!moving && reason == CameraMoveStartedReason.GESTURE) select(camera.position.target, true)
        }
    }
    Scaffold(topBar = { TopAppBar(title = { Text("Choose pickup") }, navigationIcon = {
        IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back without changing pickup") }
    }) }) { padding ->
        Column(Modifier.padding(padding).consumeWindowInsets(padding).imePadding().fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Where should your driver meet you?", style = MaterialTheme.typography.titleLarge)
            OutlinedButton(onClick = { consumedSearch = null; onSearch() }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Search, null); Spacer(Modifier.width(8.dp)); Text("Search address, building or place")
            }
            OutlinedButton(enabled = !locating, onClick = {
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                    ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) locate()
                else permission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
            }, modifier = Modifier.fillMaxWidth()) { Text(if (locating) "Finding your location…" else "Use current location") }
            if (googleMapsConfigured()) {
                Box(Modifier.fillMaxWidth().height(260.dp)) {
                    GoogleMap(Modifier.fillMaxSize(), cameraPositionState = camera,
                        onMapLoaded = { loaded = true }, onMapClick = { select(it, true); moveTo = it },
                        uiSettings = MapUiSettings(zoomControlsEnabled = true, mapToolbarEnabled = false)) {
                        if (latitude != null && longitude != null) Marker(state = rememberUpdatedMarkerState(LatLng(latitude!!, longitude!!)), title = "Pickup", snippet = address)
                    }
                    Icon(Icons.Default.AddLocationAlt, "Move the map to choose pickup", Modifier.align(Alignment.Center).size(32.dp), tint = MaterialTheme.colorScheme.primary)
                }
                Text("Move the map or tap a point, then confirm the pickup below.", style = MaterialTheme.typography.bodySmall)
            } else Text("Map is unavailable. Check Maps configuration; address search also requires the configured Places service.")
            if (latitude != null && longitude != null) Text(address.ifBlank { name }, style = MaterialTheme.typography.titleMedium)
            issue?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
            OutlinedTextField(notes, { notes = it.take(280) }, label = { Text("Pickup instructions (optional)") },
                placeholder = { Text("Main entrance, next to the lobby…") }, supportingText = { Text("${notes.length}/280 · Visible to your assigned driver") },
                modifier = Modifier.fillMaxWidth(), minLines = 2, maxLines = 4)
            Button(enabled = latitude != null && longitude != null && !locating && !camera.isMoving, modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp), onClick = {
                onConfirm(PlaceSuggestion(name = name.ifBlank { "Selected pickup" }, address = address, latitude = latitude, longitude = longitude), manual, notes.trim())
            }) { Text("Confirm pickup") }
            Text("Changing pickup refreshes the route and fare. No ride is booked by this button.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
internal fun PickupWaitingMessage43(endsAt: Long?) {
    var now by remember(endsAt) { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(endsAt) { while (endsAt != null) { now = System.currentTimeMillis(); delay(1_000) } }
    endsAt?.let {
        val seconds = ((it - now + 999) / 1_000).coerceAtLeast(0)
        Text(if (seconds > 0) "Waiting window · ${seconds / 60}:${(seconds % 60).toString().padStart(2, '0')} remaining"
             else "Waiting window elapsed. Your driver may end the pickup if they cannot find you.", style = MaterialTheme.typography.bodyMedium)
    }
}
