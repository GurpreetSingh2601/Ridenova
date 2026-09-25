package com.ridenova.driver.location

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.core.app.ServiceCompat
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.ridenova.driver.BuildConfig
import com.ridenova.driver.MainActivity
import com.ridenova.driver.data.DriverHttpApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.cancelChildren
import org.json.JSONObject

/**
 * Build 23 foreground location service.
 *
 * While a development driver is online, this service continues publishing the latest GPS position
 * even if the Driver activity is backgrounded (for example, while Google Maps navigation is open).
 * The backend associates presence with an assigned ride and exposes it to the passenger app.
 */
class DriverLocationService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val client by lazy { LocationServices.getFusedLocationProviderClient(this) }
    private var callback: LocationCallback? = null
    private var publishJob: Job? = null
    private var api: DriverHttpApi? = null
    private var offerJob: Job? = null
    private var notifiedLease: String? = null
    private val overlay by lazy { DriverOverlay(this) }

    override fun onCreate() {
        super.onCreate()
        createChannel()
        val token = com.ridenova.driver.data.FleetCredentials(this).load()
        if (BuildConfig.RIDENOVA_DEV_URL.isNotBlank() && (token.isNotBlank() || (BuildConfig.RIDENOVA_LEGACY_DRIVER && BuildConfig.RIDENOVA_DEV_TOKEN.isNotBlank()))) {
            api = DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL, token.ifBlank { BuildConfig.RIDENOVA_DEV_TOKEN }, token.isNotBlank())
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopTracking()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
                return START_NOT_STICKY
            }
            else -> startTracking()
        }
        // The system may recreate the already-running online session after process pressure.
        // New starts still originate from a visible Driver screen to satisfy Android's
        // while-in-use location and foreground-service launch restrictions.
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        stopTracking()
        overlay.hide()
        DriverAlerts.clear(this)
        scope.coroutineContext.cancelChildren()
        super.onDestroy()
    }

    private fun startTracking() {
        if (callback != null) return
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            notification("Connecting · checking driver status"),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
            } else 0
        )
        startOfferMonitoring()
        val fine = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarse = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (!fine && !coarse) {
            stopSelf()
            return
        }
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 4_000L)
            .setMinUpdateIntervalMillis(2_000L)
            .setMinUpdateDistanceMeters(0f)
            .build()
        val cb = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                val location = result.lastLocation ?: return
                val transport = api ?: return
                if (publishJob?.isActive == true) return
                publishJob = scope.launch {
                    try {
                        transport.json("POST", "v1/driver/location", JSONObject()
                            .put("latitude", location.latitude)
                            .put("longitude", location.longitude)
                            .put("recordedAtEpochMs", System.currentTimeMillis()))
                    } catch (ex: kotlinx.coroutines.CancellationException) { throw ex }
                    catch (ex: com.ridenova.driver.data.DriverApiException) {
                        if (ex.status == 401 || (ex.status == 409 && ex.code == "DRIVER_OFFLINE")) { stopForeground(STOP_FOREGROUND_REMOVE); stopSelf() }
                    } catch (_: Exception) { /* Retry with the next location update after network loss. */ }

                }
            }
        }
        callback = cb
        client.requestLocationUpdates(request, cb, mainLooper)
    }

    private fun stopTracking() {
        callback?.let(client::removeLocationUpdates)
        callback = null
        publishJob?.cancel()
        publishJob = null
        offerJob?.cancel(); offerJob = null
        DriverAlerts.clear(this)
        overlay.hide()
    }

    private fun startOfferMonitoring() {
        if (offerJob?.isActive == true) return
        offerJob = scope.launch {
            var consecutiveFailures = 0
            while (true) {
                try {
                    val transport = api ?: break
                    val status = transport.json("GET", "v1/driver/status")
                    consecutiveFailures = 0
                    val active = status.optString("activeRideId").let { it.isNotBlank() && it != "null" }
                    if (!status.optBoolean("online") && !active) {
                        withContext(Dispatchers.Main) { overlay.hide(); DriverAlerts.clear(this@DriverLocationService); stopForeground(STOP_FOREGROUND_REMOVE); stopSelf() }
                        break
                    }
                    val offer = if (!active) transport.json("GET", "v1/driver/requests/current") else JSONObject()
                    val expires = offer.optLong("expiresAtEpochMs", 0L)
                    val valid = offer.optString("id").isNotBlank() && expires > System.currentTimeMillis()
                    val lease = if (valid) offer.optString("id") + ":" + expires else null
                    withContext(Dispatchers.Main) {
                        val locked = getSystemService(android.app.KeyguardManager::class.java).isKeyguardLocked
                        if (DriverVisibility.foreground || !valid) {
                            DriverAlerts.clear(this@DriverLocationService)
                            if (!valid) notifiedLease = null
                        } else if (lease != notifiedLease) {
                            DriverAlerts.show(this@DriverLocationService, offer); notifiedLease = lease
                        }
                        overlay.update(valid && !locked)
                        val text = when {
                            active -> "Trip in progress · tap to return"
                            status.optString("dispatchReason") == "LOCATION_STALE" -> "GPS is stale · waiting for location"
                            status.optString("dispatchReason") == "LOCATION_REQUIRED" -> "Waiting for GPS · keep location enabled"
                            else -> "Online · listening for ride requests"
                        }
                        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(text))
                    }
                } catch (ex: kotlinx.coroutines.CancellationException) { throw ex }
                catch (ex: com.ridenova.driver.data.DriverApiException) {
                    consecutiveFailures++
                    withContext(Dispatchers.Main) {
                        DriverAlerts.clear(this@DriverLocationService); overlay.hide(); notifiedLease = null
                        if (ex.status == 401) { stopForeground(STOP_FOREGROUND_REMOVE); stopSelf() }
                        else getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification("Connection unavailable · retrying"))
                    }
                    if (ex.status == 401) break
                } catch (_: Exception) {
                    consecutiveFailures++
                    withContext(Dispatchers.Main) {
                        DriverAlerts.clear(this@DriverLocationService); overlay.hide(); notifiedLease = null
                        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification("Connection lost · reconnecting"))
                    }
                }
                // Back off during prolonged outages instead of hammering the server.
                // Successful status polling immediately resets to the normal 2s cadence.
                delay(when {
                    consecutiveFailures >= 6 -> 15_000L
                    consecutiveFailures >= 3 -> 6_000L
                    else -> 2_000L
                })
            }
        }
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(NotificationChannel(
                CHANNEL_ID,
                "Driver location",
                NotificationManager.IMPORTANCE_LOW
            ).apply { description = "Keeps RideNova Driver location active while online" })
        }
    }

    private fun notification(text: String) = NotificationCompat.Builder(this, CHANNEL_ID)
        .setSmallIcon(com.ridenova.driver.R.drawable.ic_ridenova_notification)
        .setContentTitle("RideNova Driver")
        .setContentText(text)
        .setOngoing(true)
        .setCategory(NotificationCompat.CATEGORY_SERVICE)
        .setOnlyAlertOnce(true)
        .setContentIntent(PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        ))
        .build()

    companion object {
        private const val CHANNEL_ID = "ridenova_driver_location"
        private const val NOTIFICATION_ID = 2301
        private const val ACTION_START = "com.ridenova.driver.START_LOCATION"
        private const val ACTION_STOP = "com.ridenova.driver.STOP_LOCATION"

        fun start(context: Context) {
            ContextCompat.startForegroundService(context, Intent(context, DriverLocationService::class.java).setAction(ACTION_START))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, DriverLocationService::class.java))
        }
    }
}
