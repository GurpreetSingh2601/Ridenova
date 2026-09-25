package com.ridenova.driver.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.app.NotificationManagerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner

@Composable
fun DriverAlertSettings() {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("driver_display", Context.MODE_PRIVATE) }
    var enabled by remember { mutableStateOf(prefs.getBoolean("floating_shortcut", false)) }
    var allowed by remember { mutableStateOf(Settings.canDrawOverlays(context)) }
    var notifications by remember { mutableStateOf(NotificationManagerCompat.from(context).areNotificationsEnabled()) }
    val lifecycle = LocalLifecycleOwner.current
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                allowed = Settings.canDrawOverlays(context)
                notifications = NotificationManagerCompat.from(context).areNotificationsEnabled()
            }
        }
        lifecycle.lifecycle.addObserver(observer)
        onDispose { lifecycle.lifecycle.removeObserver(observer) }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Stay reachable", style = MaterialTheme.typography.headlineSmall)
        Text("When you're online, RideNova can alert you to new requests while you use another app. Tap an alert to review the fare and route.")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Ride request notifications", style = MaterialTheme.typography.titleMedium)
                Text(if (notifications) "Notifications are allowed. Check that Incoming ride requests is enabled with pop-ups and sound."
                    else "Notifications are off. Enable them to receive request alerts outside RideNova.")
                OutlinedButton(onClick = {
                    context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
                }, modifier = Modifier.fillMaxWidth()) { Text("Notification settings") }
            }
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Text("Floating shortcut", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                    Switch(checked = enabled, onCheckedChange = {
                        enabled = it; prefs.edit().putBoolean("floating_shortcut", it).apply()
                        if (it && !allowed) context.startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${context.packageName}")))
                    })
                }
                Text("A small RideNova button appears over other apps while you are online. Drag it to move; tap to return to Driver. It hides inside RideNova, on the lock screen, and when you go offline.")
                if (enabled && !allowed) {
                    Text("Allow Display over other apps to enable the shortcut.", color = MaterialTheme.colorScheme.error)
                    OutlinedButton(onClick = { context.startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${context.packageName}"))) }) { Text("Allow floating shortcut") }
                }
            }
        }
        Text("Keep location enabled. Go online while RideNova is open so Android can start its foreground location service. Force-stopping the app ends listening; reopen it to reconnect. Alerts also require a connection to your shared server.", style = MaterialTheme.typography.bodySmall)
        Text("Pop-ups and sound follow your Android notification and Do Not Disturb settings. No automatic acceptance or forced full-screen interruptions.", style = MaterialTheme.typography.bodySmall)
    }
}
