package com.ridenova.driver.location

import android.Manifest
import android.app.*
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.ridenova.driver.MainActivity
import com.ridenova.driver.R
import org.json.JSONObject
import java.text.NumberFormat
import java.util.Locale

object DriverVisibility { @Volatile var foreground = false }

object DriverAlerts {
    private const val CHANNEL = "ridenova_requests_31_1"
    private const val ID = 3112
    fun clear(context: Context) { context.getSystemService(NotificationManager::class.java).cancel(ID) }
    fun show(context: Context, offer: JSONObject) {
        val remaining = offer.optLong("expiresAtEpochMs") - System.currentTimeMillis()
        if (remaining <= 0) { clear(context); return }
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Incoming ride requests", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Time-limited ride offers while you are online"
            enableVibration(true)
            lockscreenVisibility = Notification.VISIBILITY_PRIVATE
        })
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val open = PendingIntent.getActivity(context, 3112, Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val amount = NumberFormat.getCurrencyInstance(Locale.CANADA).format(offer.optDouble("driverEstimatedEarningsCad"))
        val pickup = "${offer.optInt("pickupEtaMin")} min · ${offer.optDouble("pickupDistanceKm")} km to pickup"
        val publicVersion = NotificationCompat.Builder(context, CHANNEL).setSmallIcon(R.drawable.ic_ridenova_notification)
            .setContentTitle("RideNova · new ride request").setContentText("Unlock to review").build()
        manager.notify(ID, NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_ridenova_notification).setContentTitle("RideNova · $amount estimated")
            .setContentText(pickup)
            .setStyle(NotificationCompat.BigTextStyle().bigText("$pickup\n${offer.optString("pickupName")} → ${offer.optString("destinationName")}\nTap to review before it expires."))
            .setCategory(NotificationCompat.CATEGORY_EVENT).setPriority(NotificationCompat.PRIORITY_HIGH)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE).setPublicVersion(publicVersion)
            .setContentIntent(open).setAutoCancel(true).setTimeoutAfter(remaining).build())
    }
}
