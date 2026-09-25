package com.ridenova.passenger.data

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import com.ridenova.passenger.BuildConfig
import com.ridenova.passenger.model.PlaceSuggestion
import com.ridenova.passenger.model.RouteChoices
import com.ridenova.passenger.model.RouteEstimate
import com.ridenova.passenger.model.RoutePoint
import com.ridenova.passenger.model.RouteType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import kotlin.math.ceil

/**
 * Development-only direct call to Google Routes API.
 *
 * v0.7 requests Google's highest-quality live-traffic routing, alternatives, and a
 * shorter-distance reference route. RideNova defaults to the fastest returned ETA.
 * Production RideNova should proxy routing through the backend so routing policy,
 * pricing, quotas, observability, and credentials are server controlled.
 */
object GoogleRoutesService {
    private const val ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"

    suspend fun computeDrivingRoutes(
        context: Context,
        pickup: PlaceSuggestion,
        destination: PlaceSuggestion?
    ): Result<RouteChoices> = withContext(Dispatchers.IO) {
        runCatching {
            val destinationValue = destination ?: error("Destination unavailable")
            check(BuildConfig.MAPS_API_KEY.isNotBlank() && BuildConfig.MAPS_API_KEY != "YOUR_API_KEY") {
                "Google Maps API key is not configured"
            }

            val body = JSONObject().apply {
                put("origin", waypoint(pickup))
                put("destination", waypoint(destinationValue))
                put("travelMode", "DRIVE")
                // Use Google's live traffic model. Keep the request intentionally conservative: the
                // SHORTER_DISTANCE reference-route option caused some development keys/regions to
                // reject the whole request, which silently pushed the app onto its prototype ETA.
                put("routingPreference", "TRAFFIC_AWARE")
                put("computeAlternativeRoutes", true)
                put("polylineQuality", "HIGH_QUALITY")
                put("polylineEncoding", "ENCODED_POLYLINE")
            }.toString()

            val connection = (URL(ENDPOINT).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 15_000
                readTimeout = 20_000
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("X-Goog-Api-Key", BuildConfig.MAPS_API_KEY)
                setRequestProperty(
                    "X-Goog-FieldMask",
                    "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.routeLabels,routes.routeToken"
                )
                setRequestProperty("X-Android-Package", context.packageName)
                androidCertificateSha1(context)?.let { setRequestProperty("X-Android-Cert", it) }
            }

            connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val status = connection.responseCode
            val responseText = (if (status in 200..299) connection.inputStream else connection.errorStream)
                ?.bufferedReader()?.use { it.readText() }.orEmpty()
            connection.disconnect()

            if (status !in 200..299) {
                val message = runCatching {
                    JSONObject(responseText).optJSONObject("error")?.optString("message")
                }.getOrNull().orEmpty()
                error(if (message.isNotBlank()) message else "Routes API HTTP $status")
            }

            val routesJson = JSONObject(responseText).optJSONArray("routes")
                ?: error("Routes API returned no routes")
            check(routesJson.length() > 0) { "Routes API returned no routes" }

            val parsed = buildList {
                for (i in 0 until routesJson.length()) {
                    val route = routesJson.getJSONObject(i)
                    val labels = route.optJSONArray("routeLabels").toStringList()
                    val type = when {
                        labels.contains("SHORTER_DISTANCE") -> RouteType.SHORTEST
                        labels.contains("DEFAULT_ROUTE") -> RouteType.FASTEST
                        else -> RouteType.ALTERNATIVE
                    }
                    add(parseRoute(route, type))
                }
            }

            // Fastest must truly be the lowest traffic-aware ETA among every returned route.
            // A SHORTER_DISTANCE reference route can occasionally also be the quickest route,
            // so excluding it would make a route labelled "Fastest" slower than another option.
            val fastest = parsed.minBy { it.durationMinutes }.copy(routeType = RouteType.FASTEST)

            // Prefer Google's explicit SHORTER_DISTANCE reference route. If unavailable, use the
            // shortest returned alternative, but only expose it when it is meaningfully different.
            val explicitShortest = parsed
                .filter { it.routeType == RouteType.SHORTEST }
                .minByOrNull { it.distanceKm }
            val candidateShortest = explicitShortest ?: parsed.minByOrNull { it.distanceKm }
            val shortest = candidateShortest?.takeIf {
                kotlin.math.abs(it.distanceKm - fastest.distanceKm) >= 0.2 ||
                    kotlin.math.abs(it.durationMinutes - fastest.durationMinutes) >= 2
            }?.copy(routeType = RouteType.SHORTEST)

            val alternatives = parsed
                .filter { it != fastest && it != candidateShortest }
                .sortedBy { it.durationMinutes }
                .map { it.copy(routeType = RouteType.ALTERNATIVE) }

            val uniqueRoutes = parsed.distinctBy {
                "${(it.distanceKm * 10).toInt()}-${it.durationMinutes}"
            }
            fun economyPrototypeFare(route: RouteEstimate): Double =
                3.25 + route.distanceKm * 1.05 + route.durationMinutes * 0.32 + 2.50

            val pocket = uniqueRoutes.minByOrNull(::economyPrototypeFare)?.copy(routeType = RouteType.POCKET)
            val fastestMinutes = fastest.durationMinutes.coerceAtLeast(1).toDouble()
            val cheapestFare = uniqueRoutes.minOfOrNull(::economyPrototypeFare)?.coerceAtLeast(1.0) ?: 1.0
            // "Best" is a balanced recommendation, but never allow it to become an obviously
            // poor time choice. This keeps the recommendation useful during congestion while
            // naturally collapsing to the fastest route when traffic is light.
            val reasonableBestPool = uniqueRoutes.filter { route ->
                route.durationMinutes <= fastest.durationMinutes + maxOf(4, kotlin.math.ceil(fastest.durationMinutes * 0.12).toInt())
            }.ifEmpty { uniqueRoutes }
            val best = reasonableBestPool.minByOrNull { route ->
                val timeRatio = route.durationMinutes / fastestMinutes
                val fareRatio = economyPrototypeFare(route) / cheapestFare
                (timeRatio * 0.68) + (fareRatio * 0.32)
            }?.copy(routeType = RouteType.BEST) ?: fastest.copy(routeType = RouteType.BEST)

            RouteChoices(
                fastest = fastest,
                shortest = shortest,
                alternatives = alternatives,
                best = best,
                pocketFriendly = pocket
            )
        }
    }

    private fun parseRoute(route: JSONObject, type: RouteType): RouteEstimate {
        val distanceMeters = route.getDouble("distanceMeters")
        val durationSeconds = parseDurationSeconds(route.getString("duration"))
        val encoded = route.getJSONObject("polyline").getString("encodedPolyline")
        return RouteEstimate(
            distanceKm = distanceMeters / 1000.0,
            durationMinutes = maxOf(1, ceil(durationSeconds / 60.0).toInt()),
            isApproximate = false,
            path = decodePolyline(encoded),
            routeType = type
        )
    }

    /** Place IDs are preferred for POIs because Google can route to an appropriate access point. */
    private fun waypoint(place: PlaceSuggestion): JSONObject {
        val placeId = place.placeId?.takeIf { it.isNotBlank() }
        if (placeId != null) return JSONObject().put("placeId", placeId)

        val latitude = place.latitude ?: error("${place.name} latitude unavailable")
        val longitude = place.longitude ?: error("${place.name} longitude unavailable")
        return JSONObject().apply {
            put("location", JSONObject().apply {
                put("latLng", JSONObject().apply {
                    put("latitude", latitude)
                    put("longitude", longitude)
                })
            })
        }
    }

    private fun JSONArray?.toStringList(): List<String> {
        if (this == null) return emptyList()
        return buildList {
            for (i in 0 until length()) add(optString(i))
        }
    }

    private fun parseDurationSeconds(value: String): Double =
        value.removeSuffix("s").toDoubleOrNull() ?: 0.0

    private fun androidCertificateSha1(context: Context): String? = runCatching {
        val packageInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.packageManager.getPackageInfo(
                context.packageName,
                PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong())
            )
        } else {
            @Suppress("DEPRECATION")
            context.packageManager.getPackageInfo(context.packageName,
                if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES)
        }
        val signatures = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            packageInfo.signingInfo?.apkContentsSigners
        } else {
            @Suppress("DEPRECATION")
            packageInfo.signatures
        }
        val certificate = signatures?.firstOrNull()?.toByteArray() ?: return@runCatching null
        MessageDigest.getInstance("SHA-1")
            .digest(certificate)
            .joinToString(separator = "") { "%02X".format(it) }
    }.getOrNull()

    /** Decode a Google encoded polyline into latitude/longitude points. */
    private fun decodePolyline(encoded: String): List<RoutePoint> {
        val points = ArrayList<RoutePoint>()
        var index = 0
        var lat = 0
        var lng = 0
        while (index < encoded.length) {
            var result = 0
            var shift = 0
            var b: Int
            do {
                b = encoded[index++].code - 63
                result = result or ((b and 0x1f) shl shift)
                shift += 5
            } while (b >= 0x20 && index < encoded.length)
            val dLat = if ((result and 1) != 0) (result shr 1).inv() else result shr 1
            lat += dLat

            result = 0
            shift = 0
            do {
                b = encoded[index++].code - 63
                result = result or ((b and 0x1f) shl shift)
                shift += 5
            } while (b >= 0x20 && index < encoded.length)
            val dLng = if ((result and 1) != 0) (result shr 1).inv() else result shr 1
            lng += dLng

            points += RoutePoint(lat / 1E5, lng / 1E5)
        }
        return points
    }
}
