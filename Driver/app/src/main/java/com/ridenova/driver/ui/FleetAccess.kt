package com.ridenova.driver.ui

import android.app.Application
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.lifecycle.ViewModelStoreOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ridenova.driver.BuildConfig
import com.ridenova.driver.R
import com.ridenova.driver.data.DriverApiException
import com.ridenova.driver.data.DriverHttpApi
import com.ridenova.driver.data.FleetCredentials
import com.ridenova.driver.location.DriverLocationService
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

@Composable
fun FleetEntry(content: @Composable (DriverViewModel, () -> Unit) -> Unit) {
    val context = LocalContext.current
    val credentials = remember { FleetCredentials(context.applicationContext) }
    var token by remember { mutableStateOf(credentials.load()) }
    val legacy = BuildConfig.RIDENOVA_DEV_URL.isBlank() ||
        (BuildConfig.RIDENOVA_LEGACY_DRIVER && BuildConfig.RIDENOVA_DEV_TOKEN.isNotBlank())
    if (token.isNotBlank() || legacy) {
        val owner = remember(token) { object : ViewModelStoreOwner { override val viewModelStore = ViewModelStore() } }
        DisposableEffect(owner) { onDispose { owner.viewModelStore.clear() } }
        val model: DriverViewModel = viewModel(viewModelStoreOwner = owner,
            factory = ViewModelProvider.AndroidViewModelFactory.getInstance(context.applicationContext as Application))
        content(model) { token = "" }
    } else FleetSignIn { saved -> token = saved }
}

@Composable
private fun FleetSignIn(onAuthenticated: (String) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val credentials = remember { FleetCredentials(context.applicationContext) }
    val focus = LocalFocusManager.current
    val passwordFocus = remember { FocusRequester() }
    var mode by rememberSaveable { mutableStateOf("Sign in") }
    var identifier by rememberSaveable { mutableStateOf("") }
    var username by rememberSaveable { mutableStateOf("") }
    var phone by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var confirmation by rememberSaveable { mutableStateOf("") }
    var name by rememberSaveable { mutableStateOf("") }
    var vehicle by rememberSaveable { mutableStateOf("") }
    var plate by rememberSaveable { mutableStateOf("") }
    var recovery by rememberSaveable { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val create = mode == "Create account"
    val recover = mode == "Recover access"
    val valid = when {
        busy -> false
        create -> username.isNotBlank() && phone.filter(Char::isDigit).length >= 10 && name.isNotBlank() &&
            vehicle.isNotBlank() && plate.isNotBlank() && password.length >= 10 && password == confirmation
        recover -> identifier.isNotBlank() && recovery.isNotBlank() && password.length >= 10 && password == confirmation
        else -> identifier.isNotBlank() && password.isNotBlank()
    }
    val listState = rememberLazyListState()
    LaunchedEffect(mode) { listState.scrollToItem(0) }

    fun changeMode(next: String) {
        mode = next; password = ""; confirmation = ""; recovery = ""; error = null
        focus.clearFocus()
    }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Scaffold(containerColor = MaterialTheme.colorScheme.background,
            contentWindowInsets = WindowInsets.safeDrawing) { safePadding ->
            LazyColumn(
                state = listState,
                modifier = Modifier.fillMaxSize().padding(safePadding).consumeWindowInsets(safePadding).imePadding(),
                contentPadding = PaddingValues(start = 22.dp, top = 20.dp, end = 22.dp, bottom = 48.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                item {
                    Row(Modifier.fillMaxWidth().padding(vertical=8.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(12.dp)) {
                        NovaBrand(48);Column { Text("RideNova",style=MaterialTheme.typography.titleLarge);Text("DRIVER",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.primary) }
                    }
                }
                item {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        (if (BuildConfig.RIDENOVA_ENVIRONMENT == "staging") listOf("Sign in") else listOf("Sign in", "Create account")).forEach { label ->
                            FilterChip(selected = mode == label, enabled = !busy,
                                onClick = { changeMode(label) }, label = { Text(label) })
                        }
                    }
                }
                item {
                    NovaSection(if(recover) "Let’s get you back in" else if(create) "Start your driver journey" else "Welcome back",if(recover) "Use your recovery credential to set a new password." else if(create) "Create your account, then submit your documents for review." else "Sign in to see your trips and earnings.")
                }
                if (create) {
                    item { AccessField(username, { username = it.take(40) }, "Username", Icons.Default.Person,
                        "3–40 letters, numbers, dots, underscores or hyphens", !busy,
                        KeyboardOptions(imeAction = ImeAction.Next)) }
                    item { AccessField(phone, { phone = it.take(20) }, "Canadian mobile number", Icons.Default.Phone,
                        "Use this number to sign in to your account", !busy,
                        KeyboardOptions(keyboardType = KeyboardType.Phone, imeAction = ImeAction.Next)) }
                } else {
                    item { AccessField(identifier, { identifier = it.take(50) }, "Username or phone", Icons.Default.Badge,
                        if (recover) "Use the identifier linked to the account" else "Phone numbers can include spaces or dashes",
                        !busy, KeyboardOptions(imeAction = ImeAction.Next),
                        KeyboardActions(onNext = { passwordFocus.requestFocus() })) }
                }
                item {
                    PasswordField(password, { password = it.take(128) },
                        if (recover) "New password" else "Password", !busy,
                        Modifier.fillMaxWidth().focusRequester(passwordFocus), if(create || recover) ImeAction.Next else ImeAction.Done)
                }
                if (create || recover) {
                    item { PasswordField(confirmation, { confirmation = it.take(128) }, "Confirm password", !busy,
                        Modifier.fillMaxWidth(), ImeAction.Next) }
                    item {
                        Text(if(confirmation.isNotEmpty() && password!=confirmation) "Passwords don’t match yet." else "Use 10–128 characters. Both passwords must match.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                if (create) {
                    item { HorizontalDivider() }
                    item { NovaSection("Driver & vehicle","Tell us who’s driving and which vehicle you’ll use.") }
                    item { AccessField(name, { name = it.take(80) }, "Full driver name", Icons.Default.DriveEta,
                        null, !busy, KeyboardOptions(imeAction = ImeAction.Next)) }
                    item { AccessField(vehicle, { vehicle = it.take(100) }, "Vehicle", Icons.Default.DirectionsCar,
                        "Example: 2023 Honda Civic · Black", !busy, KeyboardOptions(imeAction = ImeAction.Next)) }
                    item { AccessField(plate, { plate = it.uppercase().take(20) }, "Licence plate", Icons.Default.ConfirmationNumber,
                        null, !busy, KeyboardOptions(imeAction = ImeAction.Done),
                        KeyboardActions(onDone = { focus.clearFocus() })) }
                    item {
                        Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.secondaryContainer) {
                            Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.Top,
                                horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                Icon(Icons.Default.VerifiedUser, null)
                                Column {
                                    Text("Ride eligibility is reviewed", fontWeight = FontWeight.Bold)
                                    Text("Every approved driver starts with Economy. RideNova operations assigns Comfort or XL after reviewing the vehicle, capacity, documents and service rating.",
                                        style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                }
                if (recover) {
                    item {
                        Text("Enter the one-time recovery credential created by the development admin. It is never your admin token.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    item { PasswordField(recovery, { recovery = it.take(256) }, "Recovery credential", !busy,
                        Modifier.fillMaxWidth(), ImeAction.Done) }
                }
                error?.let { message ->
                    item {
                        Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.errorContainer) {
                            Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                Icon(Icons.Default.ErrorOutline, null, tint = MaterialTheme.colorScheme.onErrorContainer)
                                Text(message, color = MaterialTheme.colorScheme.onErrorContainer, modifier = Modifier.weight(1f))
                            }
                        }
                    }
                }
                item {
                    Button(enabled = valid, modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp), onClick = {
                        error = null
                        if ((create || recover) && password != confirmation) error = "Passwords do not match"
                        else if ((create || recover) && password.length < 10) error = "Use at least 10 characters"
                        else {
                            focus.clearFocus(); busy = true
                            scope.launch {
                                try {
                                    val action = when (mode) { "Create account" -> "register"; "Recover access" -> "recover"; else -> "login" }
                                    val body = JSONObject().put("password", password)
                                    if (action == "login") body.put("identifier", identifier.trim())
                                    if (action == "register") body.put("username", username.trim()).put("phone", phone.trim())
                                        .put("name", name.trim()).put("vehicle", vehicle.trim()).put("plate", plate.trim())
                                    if (action == "recover") body.put("identifier", identifier.trim()).put("recoveryToken", recovery.trim())
                                    val result = DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL, "").json("POST", "v2/fleet/auth/$action", body)
                                    val token = result.getString("developmentToken")
                                    DriverLocationService.stop(context)
                                    withContext(Dispatchers.IO) { credentials.clearAccountCache(); credentials.save(token) }
                                    password = ""; confirmation = ""; recovery = ""
                                    onAuthenticated(token)
                                } catch (ex: CancellationException) { throw ex }
                                catch (ex: Exception) { error = ex.localizedMessage ?: "Could not connect to RideNova" }
                                finally { busy = false }
                            }
                        }
                    }) {
                        if (busy) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary)
                        else Text(if (recover) "Recover account" else mode)
                    }
                }
                if (!create && BuildConfig.RIDENOVA_ENVIRONMENT != "staging") {
                    item {
                        TextButton(enabled = !busy, modifier = Modifier.fillMaxWidth(),
                            onClick = { changeMode(if (recover) "Sign in" else "Recover access") }) {
                            Text(if (recover) "Back to sign in" else "Forgot password or have a recovery credential?")
                        }
                    }
                }
                item {
                    Text(if (BuildConfig.RIDENOVA_ENVIRONMENT == "staging") "Staging · invited test accounts only. Contact the administrator for access. No real payments or payouts." else "Development build · signing in on another device replaces the previous session. No real identity verification or payout is performed.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun AccessField(value: String, onChange: (String) -> Unit, label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector, support: String?, enabled: Boolean,
    options: KeyboardOptions, actions: KeyboardActions = KeyboardActions()) {
    OutlinedTextField(value, onChange, modifier = Modifier.fillMaxWidth(), enabled = enabled, singleLine = true,
        shape=RoundedCornerShape(16.dp),label = { Text(label) }, leadingIcon = { Icon(icon, null) },
        supportingText = { if (support != null) Text(support) },
        keyboardOptions = options, keyboardActions = actions)
}

@Composable
private fun PasswordField(value: String, onChange: (String) -> Unit, label: String, enabled: Boolean,
    modifier: Modifier, action: ImeAction) {
    val focus=LocalFocusManager.current
    var visible by rememberSaveable { mutableStateOf(false) }
    OutlinedTextField(value, onChange, modifier = modifier, enabled = enabled, singleLine = true,
        shape=RoundedCornerShape(16.dp),label = { Text(label) }, leadingIcon = { Icon(Icons.Default.Lock, null) },
        visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = action),
        keyboardActions=KeyboardActions(onDone={focus.clearFocus()}),
        trailingIcon = { IconButton(onClick = { visible = !visible }) {
            Icon(if (visible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                if (visible) "Hide password" else "Show password")
        } })
}

@Composable
fun FleetAccount(model: DriverViewModel, onSignedOut: () -> Unit, onBack: () -> Unit) {
    BackHandler { onBack() }
    val context = LocalContext.current
    val api = remember { DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL, FleetCredentials(context).load(), true) }
    val scope = rememberCoroutineScope()
    val state by model.uiState.collectAsState()
    var loaded by remember { mutableStateOf(false) }
    var configured by remember { mutableStateOf(false) }
    var expired by remember { mutableStateOf(false) }
    var username by rememberSaveable { mutableStateOf("") }
    var phone by rememberSaveable { mutableStateOf("") }
    var maskedPhone by remember { mutableStateOf("") }
    var approvedDocuments by remember { mutableIntStateOf(0) }
    var completedTrips by remember { mutableIntStateOf(0) }
    var lifetimeEarnings by remember { mutableDoubleStateOf(0.0) }
    var password by rememberSaveable { mutableStateOf("") }
    var confirmation by rememberSaveable { mutableStateOf("") }
    var currentPassword by rememberSaveable { mutableStateOf("") }
    var newPassword by rememberSaveable { mutableStateOf("") }
    var newConfirmation by rememberSaveable { mutableStateOf("") }
    var changingPassword by rememberSaveable { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var confirmLogout by remember { mutableStateOf(false) }
    val activeTrip = state.rideStage in setOf(com.ridenova.driver.model.RideStage.ACCEPTED,
        com.ridenova.driver.model.RideStage.ARRIVING, com.ridenova.driver.model.RideStage.ARRIVED,
        com.ridenova.driver.model.RideStage.ON_TRIP)

    suspend fun refresh() {
        val result = api.json("GET", "v2/fleet/driver/account-overview")
        configured = result.getBoolean("loginConfigured")
        username = result.optString("username").takeUnless { it == "null" }.orEmpty()
        maskedPhone = result.optString("maskedPhone").takeUnless { it == "null" }.orEmpty()
        result.optJSONObject("documents")?.let { approvedDocuments = it.optInt("approved") }
        result.optJSONObject("lifetime")?.let {
            completedTrips = it.optInt("completedTrips")
            lifetimeEarnings = it.optDouble("estimatedEarningsCad")
        }
        loaded = true
    }
    LaunchedEffect(Unit) {
        try { refresh() }
        catch (ex: CancellationException) { throw ex }
        catch (ex: DriverApiException) { expired = ex.status == 401; error = ex.localizedMessage }
        catch (ex: Exception) { error = ex.localizedMessage }
    }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            TextButton(onClick = onBack) { Text("Back to account") }
            Text("Account & security", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            if (!loaded && error == null) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (configured) {
                Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surfaceVariant) {
                    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Signed-in driver", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text("@$username")
                        if (maskedPhone.isNotBlank()) Text(maskedPhone)
                        HorizontalDivider()
                        Text("$approvedDocuments of 4 documents approved · $completedTrips completed trips")
                        Text("Lifetime estimated earnings: CAD ${"%.2f".format(lifetimeEarnings)}",
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                OutlinedButton(onClick = { changingPassword = !changingPassword }, enabled = !busy,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 50.dp)) {
                    Icon(Icons.Default.Password, null); Spacer(Modifier.width(8.dp)); Text("Change password")
                }
                if (changingPassword) {
                    PasswordField(currentPassword, { currentPassword = it.take(128) }, "Current password", !busy,
                        Modifier.fillMaxWidth(), ImeAction.Next)
                    PasswordField(newPassword, { newPassword = it.take(128) }, "New password", !busy,
                        Modifier.fillMaxWidth(), ImeAction.Next)
                    PasswordField(newConfirmation, { newConfirmation = it.take(128) }, "Confirm new password", !busy,
                        Modifier.fillMaxWidth(), ImeAction.Done)
                    Button(enabled = !busy && newPassword.length >= 10 && newPassword == newConfirmation,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp), onClick = {
                            busy = true; error = null; message = null
                            scope.launch {
                                try {
                                    api.json("POST", "v2/fleet/driver/password", JSONObject()
                                        .put("currentPassword", currentPassword).put("newPassword", newPassword))
                                    currentPassword = ""; newPassword = ""; newConfirmation = ""
                                    changingPassword = false; message = "Password changed successfully"
                                } catch (ex: CancellationException) { throw ex }
                                catch (ex: Exception) { error = ex.localizedMessage }
                                finally { busy = false }
                            }
                        }) { Text("Save new password") }
                }
            }
            if (loaded && !configured) {
                Text("Keep this existing driver profile. Add sign-in details once, then use them on this or another phone.")
                AccessField(username, { username = it.take(40) }, "Choose username", Icons.Default.Person,
                    null, !busy, KeyboardOptions(imeAction = ImeAction.Next))
                AccessField(phone, { phone = it.take(20) }, "Canadian mobile number", Icons.Default.Phone,
                    null, !busy, KeyboardOptions(keyboardType = KeyboardType.Phone, imeAction = ImeAction.Next))
                PasswordField(password, { password = it.take(128) }, "Password · 10–128 characters", !busy,
                    Modifier.fillMaxWidth(), ImeAction.Next)
                PasswordField(confirmation, { confirmation = it.take(128) }, "Confirm password", !busy,
                    Modifier.fillMaxWidth(), ImeAction.Done)
                Button(enabled = !busy && !state.busy && username.isNotBlank() && phone.filter(Char::isDigit).length >= 10 &&
                    password.length >= 10 && password == confirmation, modifier = Modifier.fillMaxWidth(), onClick = {
                    busy = true; error = null
                    scope.launch {
                        try {
                            api.json("POST", "v2/fleet/driver/login-details", JSONObject()
                                .put("username", username.trim()).put("phone", phone.trim()).put("password", password))
                            password = ""; confirmation = ""; refresh(); message = "Sign-in details saved"
                        } catch (ex: CancellationException) { throw ex }
                        catch (ex: Exception) { error = ex.localizedMessage }
                        finally { busy = false }
                    }
                }) { Text("Save sign-in details") }
            }
            message?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            state.connectionError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            HorizontalDivider()
            Text("Logging out takes this driver offline and removes saved access from this phone. Server profile, documents and trip history remain.")
            if (activeTrip) Text("Finish or cancel the active trip before logging out.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
                enabled = (expired || !activeTrip) && !busy && !state.busy && (configured || expired),
                onClick = { confirmLogout = true }) { Text("Log out / switch account") }
            OutlinedButton(enabled = !busy && !state.busy, modifier = Modifier.fillMaxWidth(), onClick = {
                scope.launch {
                    busy = true
                    try { refresh(); error = null }
                    catch (ex: CancellationException) { throw ex }
                    catch (ex: DriverApiException) { expired = ex.status == 401; error = ex.localizedMessage }
                    catch (ex: Exception) { error = ex.localizedMessage }
                    finally { busy = false }
                }
            }) { Text("Refresh account") }
            Spacer(Modifier.height(32.dp))
        }
    }
    if (confirmLogout) AlertDialog(onDismissRequest = { confirmLogout = false },
        title = { Text("Log out of RideNova Driver?") },
        text = { Text("You can sign back in using your username or Canadian phone number.") },
        confirmButton = { TextButton(onClick = { confirmLogout = false; model.signOut(onSignedOut) }) { Text("Log out") } },
        dismissButton = { TextButton(onClick = { confirmLogout = false }) { Text("Stay signed in") } })
}
