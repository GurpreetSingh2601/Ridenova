package com.ridenova.driver.navigation

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import com.google.android.gms.maps.model.LatLng
import com.ridenova.driver.BuildConfig
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import kotlin.math.ceil

/** Build 25 BETA: Google Routes backed road geometry and instructions; never invent turn guidance. */
data class RoadStep(val instruction: String, val end: LatLng, val distanceMeters: Int)
data class RoadRoute(val points: List<LatLng>, val distanceMeters: Int, val etaMinutes: Int, val steps: List<RoadStep>)

object DriverRoadRoutes {
    private const val endpoint = "https://routes.googleapis.com/directions/v2:computeRoutes"
    suspend fun fetch(context: Context, from: LatLng, to: LatLng): Result<RoadRoute> = withContext(Dispatchers.IO) {
        runCatching {
            check(BuildConfig.MAPS_API_KEY.isNotBlank()) { "Google Routes API key missing" }
            val json = JSONObject().apply {
                put("origin", waypoint(from)); put("destination", waypoint(to))
                put("travelMode", "DRIVE"); put("routingPreference", "TRAFFIC_AWARE")
                put("polylineQuality", "HIGH_QUALITY"); put("polylineEncoding", "ENCODED_POLYLINE")
            }
            val connection = URL(endpoint).openConnection() as HttpURLConnection
            try {
                connection.requestMethod = "POST"; connection.doOutput = true
                connection.connectTimeout = 12000; connection.readTimeout = 16000
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("X-Goog-Api-Key", BuildConfig.MAPS_API_KEY)
                connection.setRequestProperty("X-Goog-FieldMask", "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline,routes.legs.steps.distanceMeters,routes.legs.steps.endLocation,routes.legs.steps.navigationInstruction.instructions")
                connection.setRequestProperty("X-Android-Package", context.packageName)
                certSha1(context)?.let { connection.setRequestProperty("X-Android-Cert", it) }
                connection.outputStream.use { it.write(json.toString().toByteArray(Charsets.UTF_8)) }
                val status = connection.responseCode
                val text = (if (status in 200..299) connection.inputStream else connection.errorStream)
                    ?.bufferedReader()?.use { it.readText() }.orEmpty()
                check(status in 200..299) {
                    JSONObject(text).optJSONObject("error")?.optString("message")?.ifBlank { "Routes HTTP $status" } ?: "Routes HTTP $status"
                }
                val route = JSONObject(text).getJSONArray("routes").getJSONObject(0)
                val steps = buildList {
                    val legs = route.optJSONArray("legs")
                    if (legs != null) for (i in 0 until legs.length()) {
                        val legSteps = legs.getJSONObject(i).optJSONArray("steps") ?: continue
                        for (j in 0 until legSteps.length()) {
                            val s = legSteps.getJSONObject(j)
                            val end = s.optJSONObject("endLocation")?.optJSONObject("latLng") ?: continue
                            add(RoadStep(s.optJSONObject("navigationInstruction")?.optString("instructions")?.takeIf { it.isNotBlank() }
                                ?: "Continue along route", LatLng(end.getDouble("latitude"),end.getDouble("longitude")),s.optInt("distanceMeters")))
                        }
                    }
                }
                RoadRoute(decode(route.getJSONObject("polyline").getString("encodedPolyline")),
                    route.getInt("distanceMeters"),
                    ceil(route.getString("duration").removeSuffix("s").toDouble() / 60).toInt().coerceAtLeast(1), steps)
            } finally { connection.disconnect() }
        }.onFailure { if (it is CancellationException) throw it }
    }
    private fun waypoint(p: LatLng) = JSONObject().put("location",JSONObject().put("latLng",JSONObject()
        .put("latitude",p.latitude).put("longitude",p.longitude)))
    private fun certSha1(context: Context): String? = runCatching {
        val info = if (Build.VERSION.SDK_INT >= 33) context.packageManager.getPackageInfo(context.packageName,
            PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()))
        else { @Suppress("DEPRECATION") context.packageManager.getPackageInfo(context.packageName,
            if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES) }
        val signatures = if (Build.VERSION.SDK_INT >= 28) info.signingInfo?.apkContentsSigners
            else { @Suppress("DEPRECATION") info.signatures }
        val bytes = signatures?.firstOrNull()?.toByteArray() ?: return@runCatching null
        MessageDigest.getInstance("SHA-1").digest(bytes).joinToString("") { "%02X".format(it) }
    }.getOrNull()
    internal fun decode(encoded: String): List<LatLng> {
        val result = mutableListOf<LatLng>(); var index=0; var lat=0; var lng=0
        while (index < encoded.length) {
            fun next(): Int {
                var shift=0; var value=0; var b:Int
                do { require(index < encoded.length) { "Invalid route geometry" }; b=encoded[index++].code-63
                    value = value or ((b and 31) shl shift); shift += 5 } while (b >= 32)
                return if (value and 1 != 0) (value shr 1).inv() else value shr 1
            }
            lat += next(); lng += next(); result.add(LatLng(lat/1e5,lng/1e5))
        }
        return result
    }
}
