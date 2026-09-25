package com.ridenova.driver.ui

import androidx.activity.compose.BackHandler
import android.provider.OpenableColumns
import android.util.Base64
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.ridenova.driver.BuildConfig
import com.ridenova.driver.data.DriverHttpApi
import com.ridenova.driver.data.FleetCredentials
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

@Composable
fun FleetDocuments(onBack: () -> Unit) {
    BackHandler { onBack() }
    val context = LocalContext.current
    val api = remember { DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL, FleetCredentials(context).load(), true) }
    val scope = rememberCoroutineScope()
    var rows by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var status by remember { mutableStateOf("Loading…") }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var kind by remember { mutableStateOf("LICENCE") }
    var expiry by remember { mutableStateOf("") }
    var uploadKind by remember { mutableStateOf("") }
    var uploadExpiry by remember { mutableStateOf("") }
    var uploadRevision by remember { mutableStateOf(0) }
    suspend fun refresh() {
        val profile = api.json("GET", "v2/fleet/driver/status")
        status = profile.getString("name") + " · " + profile.getString("status")
        val array = api.json("GET", "v2/fleet/driver/documents").getJSONArray("documents")
        rows = (0 until array.length()).map { array.getJSONObject(it) }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) { busy = false } else scope.launch {
            try {
                val payload = withContext(Dispatchers.IO) {
                    val resolver = context.contentResolver
                    val bytes = resolver.openInputStream(uri)?.use { stream ->
                        val output = java.io.ByteArrayOutputStream()
                        val buffer = ByteArray(8192)
                        while (output.size() <= 2 * 1024 * 1024) {
                            val count = stream.read(buffer)
                            if (count < 0) break
                            output.write(buffer, 0, count)
                        }
                        output.toByteArray() } ?: kotlin.error("Cannot read selected file")
                    require(bytes.size <= 2 * 1024 * 1024) { "Choose a file no larger than 2 MiB" }
                    var filename = "document"
                    resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                        if (cursor.moveToFirst()) filename = cursor.getString(0)
                    }
                    JSONObject().put("filename", filename).put("mime", resolver.getType(uri) ?: "application/octet-stream")
                        .put("contentBase64", Base64.encodeToString(bytes, Base64.NO_WRAP))
                        .put("expiryDate", uploadExpiry).put("revision", uploadRevision)
                }
                api.json("POST", "v2/fleet/driver/documents/$uploadKind", payload)
                refresh(); error = null
            } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.localizedMessage } finally { busy = false }
        }
    }
    LaunchedEffect(Unit) { try { refresh() } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.localizedMessage } }
    Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        TextButton(onClick = onBack) { Text("Back to account") }
        Text("Onboarding & documents", style = MaterialTheme.typography.headlineSmall)
        DriverDocumentStatus(status)
        if (status == "Loading…" && error == null) LinearProgressIndicator(Modifier.fillMaxWidth())
        Text("Four approved, unexpired documents and admin approval are needed to receive requests. Use sample files only; this is a development review workflow.")
        val expiringSoon = rows.filter { doc ->
            val expiryDate = runCatching { java.time.LocalDate.parse(doc.optString("expiryDate")) }.getOrNull()
            expiryDate != null && !expiryDate.isAfter(java.time.LocalDate.now().plusDays(30))
        }
        if (expiringSoon.isNotEmpty()) {
            Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.errorContainer)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Documents requiring attention", style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onErrorContainer)
                    expiringSoon.forEach { doc ->
                        Text(doc.optString("kind") + " · " + doc.optString("expiryDate") +
                            " · " + doc.optString("status"), color = MaterialTheme.colorScheme.onErrorContainer)
                    }
                    Text("Expired or expiring in 30 days. Renew and wait for review; uploading does not mean approval.",
                        color = MaterialTheme.colorScheme.onErrorContainer)
                }
            }
        }
        rows.forEach { doc ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text(doc.getString("kind").lowercase().replaceFirstChar { it.titlecase() }, style = MaterialTheme.typography.titleMedium)
                    Text(doc.getString("status") + if (doc.optBoolean("expired")) " · EXPIRED" else "")
                    Text("Expiry: " + doc.optString("expiryDate", "Not set"))
                    val note = doc.optString("note").takeUnless { it == "null" || it.isBlank() }
                    note?.let { Text("Reviewer: $it") }
                }
            }
        }
        Text("Submit or replace a document", style = MaterialTheme.typography.titleMedium)
        listOf("LICENCE", "INSURANCE", "REGISTRATION", "INSPECTION").forEach { item ->
            FilterChip(selected = kind == item, onClick = { kind = item }, enabled = !busy, label = { Text(item.lowercase().replaceFirstChar { it.titlecase() }) })
        }
        OutlinedTextField(expiry, { expiry = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Expiry · YYYY-MM-DD") }, enabled = !busy, singleLine = true)
        Text("PDF, PNG or JPEG · maximum 2 MiB. Replacing a document takes you offline until it is reviewed. Finish an active trip first.")
        Button(modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp), enabled = !busy && rows.isNotEmpty() && expiry.matches(Regex("\\d{4}-\\d{2}-\\d{2}")), onClick = {
            uploadKind = kind; uploadExpiry = expiry
            uploadRevision = rows.first { it.getString("kind") == kind }.getInt("revision")
            busy = true
            picker.launch(arrayOf("application/pdf", "image/png", "image/jpeg"))
        }) { Text(if (busy) "Uploading…" else "Choose file & submit") }
        OutlinedButton(modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp), enabled = !busy, onClick = {
            busy = true
            scope.launch { try { refresh(); error = null } catch (e: CancellationException) { throw e } catch (e: Exception) { error = e.localizedMessage } finally { busy = false } }
        }) { Text("Refresh review status") }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    }
}

@Composable
private fun DriverDocumentStatus(status: String) {
    Surface(shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
        Text(status, Modifier.fillMaxWidth().padding(16.dp), style = MaterialTheme.typography.titleMedium)
    }
}
