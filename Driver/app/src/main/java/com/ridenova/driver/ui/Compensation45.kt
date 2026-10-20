package com.ridenova.driver.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.ridenova.driver.BuildConfig
import com.ridenova.driver.data.DriverHttpApi
import com.ridenova.driver.data.FleetCredentials
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.time.LocalDate
import java.time.ZoneId
import java.util.Locale

@Composable
internal fun PayPeriod45() {
    val context = LocalContext.current
    val token = remember { FleetCredentials(context).load() }
    if (token.isBlank()) return
    val api = remember(token) { DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL, token, true) }
    val scope = rememberCoroutineScope()
    val today = LocalDate.now(ZoneId.of("America/Vancouver"))
    var period by remember { mutableStateOf(today.withDayOfMonth(if (today.dayOfMonth <= 15) 1 else 16)) }
    var report by remember { mutableStateOf<JSONObject?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    suspend fun refresh() {
        busy = true
        try { report = api.json("GET", "v4/trips/driver/earnings?period=$period"); error = null }
        catch (e: CancellationException) { throw e }
        catch (e: Exception) { report = null; error = e.message ?: "Reconnect to load earnings" }
        finally { busy = false }
    }
    LaunchedEffect(period) { report = null; refresh() }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Pay period · $period", style = MaterialTheme.typography.titleMedium)
            Text("Vancouver time · includes pickup and waiting. Test accounting; no payout.")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(enabled = !busy, onClick = { period = if (period.dayOfMonth == 16) period.withDayOfMonth(1) else period.minusMonths(1).withDayOfMonth(16) }) { Text("Previous") }
                TextButton(enabled = !busy && period < today.withDayOfMonth(if(today.dayOfMonth<=15) 1 else 16), onClick = { period = if(period.dayOfMonth==1) period.withDayOfMonth(16) else period.plusMonths(1).withDayOfMonth(1) }) { Text("Next") }
                TextButton(enabled = !busy, onClick = { scope.launch { refresh() } }) { Text(if(busy) "Loading…" else "Refresh") }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            report?.let { r ->
                fun cad(key: String) = String.format(Locale.CANADA, "$%.2f", r.optLong(key)/100.0)
                listOf("Trip earnings" to "baseEarningsCents", "Bonuses" to "bonusCents", "Recorded tips" to "tipsCents",
                    "Distance allowance" to "distanceAllowanceCents", "Period minimum adjustment" to "topUpCents", "Total" to "totalCents").forEach { (label,key) ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text(label); Text(cad(key)) }
                }
                Text("${r.optLong("engagedMs")/60000} engaged minutes · ${String.format(Locale.CANADA,"%.1f",r.optLong("meters")/1000.0)} recorded km")
                Text(if (r.optBoolean("reviewRequired")) "Provisional: distance verification or an active assignment is pending." else if(!r.isNull("finalized")) "Finalized test statement" else "Provisional: period reconciliation pending.")
                Text("Mileage reimbursement is separate from earnings. The minimum adjustment can change as this period's earnings grow.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
