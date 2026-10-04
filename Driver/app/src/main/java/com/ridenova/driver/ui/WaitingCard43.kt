package com.ridenova.driver.ui

import android.os.SystemClock
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.ridenova.driver.BuildConfig
import com.ridenova.driver.data.DriverHttpApi
import com.ridenova.driver.data.FleetCredentials
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject

/** Countdown follows server snapshots; never authorizes a cancellation locally. */
@Composable
internal fun WaitingCard43(rideId: String, onCancelled: () -> Unit) {
    val context = LocalContext.current
    val api = remember { DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL, FleetCredentials(context).load(), true) }
    val scope = rememberCoroutineScope()
    var snapshot by remember(rideId) { mutableStateOf<JSONObject?>(null) }
    var receivedAt by remember { mutableLongStateOf(0L) }
    var tick by remember { mutableLongStateOf(SystemClock.elapsedRealtime()) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var confirm by rememberSaveable(rideId) { mutableStateOf(false) }
    var checked by rememberSaveable(rideId) { mutableStateOf(false) }
    var reason by rememberSaveable(rideId) { mutableStateOf("RIDER_NOT_AT_PICKUP") }
    suspend fun refresh() {
        val result = api.json("GET", "v2/fleet/driver/rides/$rideId/waiting")
        snapshot = result; receivedAt = SystemClock.elapsedRealtime(); error = null
        if (result.optString("status") == "CANCELLED_NO_SHOW") onCancelled()
    }
    LaunchedEffect(rideId) {
        while (true) {
            if (!busy) try { refresh() } catch (e: CancellationException) { throw e } catch (e: Exception) { error = "Waiting status unavailable. Reconnect before cancelling." }
            delay(5_000)
        }
    }
    LaunchedEffect(rideId) { while (true) { tick = SystemClock.elapsedRealtime(); delay(1_000) } }
    val remaining = (snapshot?.optLong("remainingSeconds", 300) ?: 300) - (tick - receivedAt).coerceAtLeast(0) / 1000
    val fresh = snapshot != null && tick - receivedAt < 12_000 && error == null
    val verified = snapshot?.optBoolean("verifiedArrival") == true
    val canCancel = fresh && snapshot?.optBoolean("canCancel") == true
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Waiting for rider", style = MaterialTheme.typography.titleMedium)
            Text(if (verified) "No-show available in ${remaining.coerceAtLeast(0) / 60}:${(remaining.coerceAtLeast(0) % 60).toString().padStart(2, '0')}" else "Verify your location at the pickup to start the five-minute timer.")
            Text("Check the pickup point and rider instructions. No waiting or no-show fee is charged in staging.", style = MaterialTheme.typography.bodySmall)
            if (!verified) OutlinedButton(enabled = fresh && !busy, onClick = {
                scope.launch { busy = true
                    try { api.json("POST", "v2/fleet/driver/rides/$rideId/arrive", JSONObject()); refresh() }
                    catch (e: Exception) { error = e.localizedMessage ?: "Could not verify arrival" }
                    finally { busy = false }
                }
            }) { Text("Verify pickup and start waiting") }
            if (verified && snapshot?.optBoolean("locationReady") != true) Text("Fresh GPS near the pickup is required to cancel as a no-show.")
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            OutlinedButton(enabled = canCancel && !busy, onClick = { confirm = true }) { Text("Rider did not arrive") }
        }
    }
    if (confirm) AlertDialog(onDismissRequest = { if (!busy) confirm = false }, title = { Text("End pickup as a no-show?") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("This ends the booking for both apps. No fee or driver earnings will be added.")
            listOf("RIDER_NOT_AT_PICKUP" to "Rider did not arrive", "CANNOT_FIND_RIDER" to "Cannot find rider at pickup").forEach { (value, label) ->
                TextButton(enabled = !busy, onClick = { reason = value }) { Text((if (reason == value) "✓ " else "") + label) }
            }
            Row { Checkbox(checked, { checked = it }, enabled = !busy); Text("I checked the pickup point and instructions.") }
            Text("Calling and messaging are not connected in this build; no contact attempt is recorded automatically.", style = MaterialTheme.typography.bodySmall)
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = {
        Button(enabled = checked && canCancel && !busy, onClick = {
            scope.launch { busy = true; error = null
                try {
                    api.json("POST", "v2/fleet/driver/rides/$rideId/no-show", JSONObject().put("reason", reason).put("confirmedPickupChecked", true))
                    confirm = false; onCancelled()
                } catch (e: Exception) { error = e.localizedMessage ?: "Could not confirm. Retry the same action safely." }
                finally { busy = false }
            }
        }) { Text(if (busy) "Confirming…" else "Confirm no-show") }
    }, dismissButton = { TextButton(enabled = !busy, onClick = { confirm = false }) { Text("Keep waiting") } })
}
