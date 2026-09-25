package com.ridenova.passenger.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Geocoder
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.GpsFixed
import androidx.compose.material3.AssistChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.MapsInitializer
import com.google.android.gms.maps.model.BitmapDescriptor
import com.google.android.gms.maps.model.BitmapDescriptorFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.MapStyleOptions
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.MapProperties
import com.google.maps.android.compose.MapUiSettings
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.Polyline
import com.google.maps.android.compose.rememberCameraPositionState
import com.google.maps.android.compose.rememberUpdatedMarkerState
import com.ridenova.passenger.BuildConfig
import com.ridenova.passenger.model.PlaceSuggestion
import com.ridenova.passenger.model.RoutePoint
import com.ridenova.passenger.ui.theme.LocalRideNovaDarkTheme
import com.ridenova.passenger.ui.theme.NovaBlue
import com.ridenova.passenger.ui.theme.NovaSuccess
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale
import kotlin.math.abs

internal fun googleMapsConfigured(): Boolean =
    BuildConfig.MAPS_API_KEY.isNotBlank() && BuildConfig.MAPS_API_KEY != "YOUR_API_KEY"

@Composable
internal fun RideNovaMap(
    modifier: Modifier = Modifier,
    pickup: PlaceSuggestion? = null,
    destination: PlaceSuggestion? = null,
    routePoints: List<RoutePoint> = emptyList(),
    driverPoint: RoutePoint? = null,
    driverTitle: String = "Development driver position",
    approachPoints: List<RoutePoint> = emptyList(),
    progressPoint: RoutePoint? = null,
    compact: Boolean = false,
    bottomContentPadding: Dp = 0.dp,
    animateRoute: Boolean = false,
    onLocationResolved: (LatLng, String?) -> Unit = { _, _ -> }
) {
    if (!googleMapsConfigured()) {
        FallbackMap(modifier = modifier, setupMessage = true)
        return
    }

    val context = LocalContext.current
    val darkTheme = LocalRideNovaDarkTheme.current
    val coroutineScope = rememberCoroutineScope()
    val fusedLocationClient = remember { LocationServices.getFusedLocationProviderClient(context) }
    var hasLocationPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        )
    }
    var currentLocation by remember { mutableStateOf<LatLng?>(null) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { result ->
        hasLocationPermission = result[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            result[Manifest.permission.ACCESS_COARSE_LOCATION] == true
    }

    val defaultCenter = LatLng(49.1913, -122.8490)
    val cameraPositionState = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(defaultCenter, if (compact) 12.5f else 13.5f)
    }
    var userMovedCamera by remember(pickup?.placeId, destination?.placeId, compact) { mutableStateOf(false) }
    LaunchedEffect(cameraPositionState) {
        snapshotFlow { cameraPositionState.cameraMoveStartedReason }.collect { reason ->
            if (reason == com.google.maps.android.compose.CameraMoveStartedReason.GESTURE) userMovedCamera = true
        }
    }

    fun publishLocation(resolved: LatLng) {
        currentLocation = resolved
        reverseGeocode(
            context = context,
            point = resolved,
            onResolved = { address -> onLocationResolved(resolved, address) },
            onLegacyLookup = {
                coroutineScope.launch {
                    val address = withContext(Dispatchers.IO) { legacyReverseGeocode(context, resolved) }
                    onLocationResolved(resolved, address)
                }
            }
        )
    }

    fun requestCurrentLocation() {
        if (!hasLocationPermission) {
            permissionLauncher.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
            return
        }
        try {
            fusedLocationClient
                .getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, null)
                .addOnSuccessListener { location ->
                    if (location != null) {
                        publishLocation(LatLng(location.latitude, location.longitude))
                    }
                }
        } catch (_: SecurityException) {
            hasLocationPermission = false
        }
    }

    LaunchedEffect(compact) {
        if (compact) return@LaunchedEffect
        if (!hasLocationPermission) {
            permissionLauncher.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
        } else {
            requestCurrentLocation()
        }
    }

    LaunchedEffect(hasLocationPermission, compact) {
        if (!compact && hasLocationPermission && currentLocation == null) requestCurrentLocation()
    }

    val pickupLatLng = pickup?.latitude?.let { lat -> pickup.longitude?.let { lng -> LatLng(lat, lng) } }
        ?: if (compact) null else currentLocation
    val destinationLatLng = destination?.latitude?.let { lat -> destination.longitude?.let { lng -> LatLng(lat, lng) } }

    LaunchedEffect(pickupLatLng, destinationLatLng, routePoints, driverPoint, approachPoints, progressPoint, compact, userMovedCamera) {
        if (userMovedCamera) return@LaunchedEffect
        if (pickupLatLng != null && destinationLatLng != null) {
            val visible = if (compact && driverPoint != null && approachPoints.size > 1)
                listOf(pickupLatLng, LatLng(driverPoint.latitude, driverPoint.longitude))
                else if (compact && progressPoint != null)
                listOf(destinationLatLng, LatLng(progressPoint.latitude, progressPoint.longitude))
                else if (compact && routePoints.size > 1)
                routePoints.map { LatLng(it.latitude, it.longitude) } + listOf(pickupLatLng, destinationLatLng)
                else listOf(pickupLatLng, destinationLatLng)
            val minLat = visible.minOf { it.latitude }
            val maxLat = visible.maxOf { it.latitude }
            val minLng = visible.minOf { it.longitude }
            val maxLng = visible.maxOf { it.longitude }
            val center = LatLng(
                (minLat + maxLat) / 2.0,
                (minLng + maxLng) / 2.0
            )
            val span = maxOf(maxLat - minLat, maxLng - minLng)
            val zoom = when {
                span < 0.015 -> if (compact) 13.4f else 14.2f
                span < 0.05 -> if (compact) 11.7f else 12.4f
                span < 0.12 -> if (compact) 10.2f else 10.8f
                else -> if (compact) 8.9f else 9.5f
            }
            cameraPositionState.animate(CameraUpdateFactory.newLatLngZoom(center, zoom))
        } else if (currentLocation != null) {
            cameraPositionState.animate(CameraUpdateFactory.newLatLngZoom(currentLocation!!, if (compact) 13.5f else 15f))
        }
    }

    val routeProgress = remember { Animatable(1f) }
    LaunchedEffect(routePoints, animateRoute) {
        if (animateRoute && routePoints.size > 1) {
            routeProgress.snapTo(0f)
            routeProgress.animateTo(
                targetValue = 1f,
                animationSpec = tween(durationMillis = 1100, easing = FastOutSlowInEasing)
            )
        } else {
            routeProgress.snapTo(1f)
        }
    }

    val visibleRoutePoints = if (animateRoute && routePoints.size > 1) {
        val visibleCount = ((routePoints.size - 1) * routeProgress.value)
            .toInt()
            .coerceIn(1, routePoints.size - 1) + 1
        routePoints.take(visibleCount)
    } else {
        routePoints
    }

    val mapStyleOptions = remember(darkTheme) {
        if (darkTheme) MapStyleOptions(DARK_MAP_STYLE) else null
    }
    // BitmapDescriptorFactory can throw if used before the Maps renderer is initialized.
    // Explicit initialization makes the first transition from profile -> Home safe, and
    // the null fallback lets GoogleMap render normally even if initialization is delayed.
    val customMarkerFactoryReady = remember(context) {
        runCatching {
            MapsInitializer.initialize(context.applicationContext)
            true
        }.getOrDefault(false)
    }
    val pickupMarker = remember(customMarkerFactoryReady) {
        if (customMarkerFactoryReady) runCatching {
            createRideNovaMarker(NovaSuccess, MarkerGlyph.PICKUP)
        }.getOrNull() else null
    }
    val destinationMarker = remember(customMarkerFactoryReady) {
        if (customMarkerFactoryReady) runCatching {
            createRideNovaMarker(NovaBlue, MarkerGlyph.DESTINATION)
        }.getOrNull() else null
    }
    val animatedDriverLatitude by animateFloatAsState(
        targetValue = (driverPoint?.latitude ?: 0.0).toFloat(),
        animationSpec = tween(durationMillis = 900, easing = FastOutSlowInEasing),
        label = "passenger-driver-latitude"
    )
    val animatedDriverLongitude by animateFloatAsState(
        targetValue = (driverPoint?.longitude ?: 0.0).toFloat(),
        animationSpec = tween(durationMillis = 900, easing = FastOutSlowInEasing),
        label = "passenger-driver-longitude"
    )
    val displayedDriverPoint = driverPoint?.let {
        LatLng(animatedDriverLatitude.toDouble(), animatedDriverLongitude.toDouble())
    }

    Box(modifier) {
        GoogleMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = cameraPositionState,
            contentPadding = PaddingValues(bottom = bottomContentPadding),
            properties = MapProperties(
                isMyLocationEnabled = hasLocationPermission && !compact,
                mapStyleOptions = mapStyleOptions
            ),
            uiSettings = MapUiSettings(
                myLocationButtonEnabled = false,
                zoomControlsEnabled = false,
                mapToolbarEnabled = false,
                compassEnabled = true,
                scrollGesturesEnabled = true,
                zoomGesturesEnabled = true,
                rotationGesturesEnabled = true,
                tiltGesturesEnabled = true
            )
        ) {
            if (pickupLatLng != null && destinationLatLng != null) {
                if (visibleRoutePoints.size > 1) {
                    Polyline(
                        points = visibleRoutePoints.map { LatLng(it.latitude, it.longitude) },
                        color = if (progressPoint != null) NovaBlue.copy(alpha = .38f) else NovaBlue,
                        width = 12f,
                        geodesic = false
                    )
                    if (progressPoint != null) {
                        fun distanceSq(index: Int): Double {
                            val p = visibleRoutePoints[index]
                            val latKm = (p.latitude - progressPoint.latitude) * 111.3
                            val lngKm = (p.longitude - progressPoint.longitude) * 111.3 * kotlin.math.cos(Math.toRadians(p.latitude))
                            return latKm * latKm + lngKm * lngKm
                        }
                        val closest = visibleRoutePoints.indices.minByOrNull(::distanceSq) ?: 0
                        // Only colour travelled road when a reported fix is near the planned route.
                        if (closest > 0 && distanceSq(closest) <= .25) Polyline(
                            points = visibleRoutePoints.take(closest + 1).map { LatLng(it.latitude, it.longitude) },
                            color = NovaSuccess, width = 12f, geodesic = false
                        )
                    }
                }
                if (approachPoints.size > 1) Polyline(
                    points = approachPoints.map { LatLng(it.latitude, it.longitude) },
                    color = NovaSuccess, width = 12f, geodesic = false
                )
                Marker(
                    state = rememberUpdatedMarkerState(position = pickupLatLng),
                    title = pickup?.name ?: "Pickup",
                    snippet = pickup?.address,
                    icon = pickupMarker,
                    anchor = androidx.compose.ui.geometry.Offset(0.5f, 0.5f)
                )
            }
            destinationLatLng?.let { position ->
                Marker(
                    state = rememberUpdatedMarkerState(position = position),
                    title = destination?.name ?: "Destination",
                    snippet = destination?.address,
                    icon = destinationMarker,
                    anchor = androidx.compose.ui.geometry.Offset(0.5f, 0.5f)
                )
            }
            displayedDriverPoint?.let { point ->
                Marker(
                    state = rememberUpdatedMarkerState(position = point),
                    title = driverTitle,
                    icon = if (customMarkerFactoryReady) BitmapDescriptorFactory.defaultMarker(BitmapDescriptorFactory.HUE_ORANGE) else null
                )
            }
        }

        if (!compact) {
            // Keep the recenter action in a protected map-only zone. Home/Work and recent
            // destination cards are drawn lower on the screen, so they can never cover it.
            androidx.compose.material3.Surface(
                onClick = {
                    userMovedCamera = false
                    requestCurrentLocation()
                    currentLocation?.let { location ->
                        coroutineScope.launch {
                            cameraPositionState.animate(CameraUpdateFactory.newLatLngZoom(location, 15f), 420)
                        }
                    }
                },
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .statusBarsPadding()
                    .padding(top = 82.dp, end = 18.dp)
                    .size(50.dp),
                shape = CircleShape,
                color = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f),
                contentColor = NovaBlue,
                shadowElevation = 10.dp,
                tonalElevation = 4.dp
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        Icons.Default.GpsFixed,
                        contentDescription = "Center on my location",
                        modifier = Modifier.size(23.dp)
                    )
                }
            }
        }
    }
}

private enum class MarkerGlyph { PICKUP, DESTINATION }

private fun createRideNovaMarker(color: Color, glyph: MarkerGlyph): BitmapDescriptor {
    val size = 68
    val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bitmap)
    val paint = Paint(Paint.ANTI_ALIAS_FLAG)

    // Soft outer halo keeps the marker visible in both light and dark map styles.
    paint.color = android.graphics.Color.argb(70, 0, 0, 0)
    canvas.drawCircle(size / 2f + 1.5f, size / 2f + 2.5f, 26f, paint)
    paint.color = android.graphics.Color.WHITE
    canvas.drawCircle(size / 2f, size / 2f, 24f, paint)
    paint.color = color.toArgb()
    canvas.drawCircle(size / 2f, size / 2f, 19f, paint)

    paint.color = android.graphics.Color.WHITE
    when (glyph) {
        MarkerGlyph.PICKUP -> {
            paint.style = Paint.Style.STROKE
            paint.strokeWidth = 4f
            canvas.drawCircle(size / 2f, size / 2f, 8f, paint)
            paint.style = Paint.Style.FILL
            canvas.drawCircle(size / 2f, size / 2f, 3.5f, paint)
        }
        MarkerGlyph.DESTINATION -> {
            val cx = size / 2f
            val cy = size / 2f
            val star = android.graphics.Path().apply {
                moveTo(cx, cy - 11f)
                lineTo(cx + 4f, cy - 4f)
                lineTo(cx + 11f, cy)
                lineTo(cx + 4f, cy + 4f)
                lineTo(cx, cy + 11f)
                lineTo(cx - 4f, cy + 4f)
                lineTo(cx - 11f, cy)
                lineTo(cx - 4f, cy - 4f)
                close()
            }
            canvas.drawPath(star, paint)
        }
    }
    return BitmapDescriptorFactory.fromBitmap(bitmap)
}

private fun reverseGeocode(
    context: Context,
    point: LatLng,
    onResolved: (String?) -> Unit,
    onLegacyLookup: () -> Unit
) {
    if (!Geocoder.isPresent()) {
        onResolved(null)
        return
    }
    val geocoder = Geocoder(context, Locale.getDefault())
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        geocoder.getFromLocation(
            point.latitude,
            point.longitude,
            1,
            object : Geocoder.GeocodeListener {
                override fun onGeocode(addresses: MutableList<android.location.Address>) {
                    onResolved(addresses.firstOrNull()?.let(::formatAddress))
                }

                override fun onError(errorMessage: String?) {
                    onResolved(null)
                }
            }
        )
    } else {
        onLegacyLookup()
    }
}

@Suppress("DEPRECATION")
private fun legacyReverseGeocode(context: Context, point: LatLng): String? {
    return runCatching {
        Geocoder(context, Locale.getDefault())
            .getFromLocation(point.latitude, point.longitude, 1)
            ?.firstOrNull()
            ?.let(::formatAddress)
    }.getOrNull()
}

private fun formatAddress(address: android.location.Address): String {
    return address.getAddressLine(0)
        ?: listOfNotNull(address.subThoroughfare, address.thoroughfare, address.locality, address.adminArea)
            .joinToString(" ")
            .ifBlank { "Current location" }
}

@Composable
private fun FallbackMap(modifier: Modifier = Modifier, setupMessage: Boolean) {
    Box(modifier.background(MaterialTheme.colorScheme.surfaceVariant)) {
        Box(
            Modifier
                .size(46.dp)
                .align(Alignment.Center)
                .clip(CircleShape)
                .background(NovaBlue.copy(alpha = .16f)),
            contentAlignment = Alignment.Center
        ) {
            Box(Modifier.size(16.dp).clip(CircleShape).background(NovaSuccess))
        }
        if (setupMessage) {
            AssistChip(
                onClick = {},
                label = { Text("Add Google Maps API key to activate live map") },
                modifier = Modifier.align(Alignment.Center).offset(y = 55.dp)
            )
        } else {
            Text(
                "Map preview",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.align(Alignment.Center)
            )
        }
    }
}

private const val DARK_MAP_STYLE = """
[
  {"elementType":"geometry","stylers":[{"color":"#171A20"}]},
  {"elementType":"labels.text.fill","stylers":[{"color":"#AEB5C2"}]},
  {"elementType":"labels.text.stroke","stylers":[{"color":"#171A20"}]},
  {"featureType":"administrative","elementType":"geometry.stroke","stylers":[{"color":"#343A45"}]},
  {"featureType":"landscape","elementType":"geometry","stylers":[{"color":"#171A20"}]},
  {"featureType":"poi","elementType":"geometry","stylers":[{"color":"#1F232B"}]},
  {"featureType":"road","elementType":"geometry","stylers":[{"color":"#303640"}]},
  {"featureType":"road","elementType":"geometry.stroke","stylers":[{"color":"#252A32"}]},
  {"featureType":"road.highway","elementType":"geometry","stylers":[{"color":"#444C59"}]},
  {"featureType":"transit","elementType":"geometry","stylers":[{"color":"#222730"}]},
  {"featureType":"water","elementType":"geometry","stylers":[{"color":"#0B2338"}]},
  {"featureType":"water","elementType":"labels.text.fill","stylers":[{"color":"#7D8A99"}]}
]
"""
