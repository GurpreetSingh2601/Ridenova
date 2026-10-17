package com.ridenova.driver.ui

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
import com.ridenova.driver.navigation.RoadRoute
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

@Composable
internal fun DriverInbox44() {
    val context=LocalContext.current
    val token=remember { FleetCredentials(context).load() }
    if(token.isBlank()){Text("Sign in to view your inbox.");return}
    val api=remember {DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL,token,true)}
    val scope=rememberCoroutineScope()
    var messages by remember {mutableStateOf<List<JSONObject>>(emptyList())}
    var error by remember {mutableStateOf<String?>(null)}
    var busy by remember {mutableStateOf(false)}
    suspend fun refresh(){busy=true;try{val a=api.json("GET","v3/operations/driver/inbox").getJSONArray("notifications");messages=(0 until a.length()).map{a.getJSONObject(it)};error=null}catch(e:CancellationException){throw e}catch(e:Exception){error=e.message}finally{busy=false}}
    LaunchedEffect(Unit){refresh()}
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
        Text("Your inbox",style=MaterialTheme.typography.headlineMedium)
        Text("Renewals, pickup check-ins and assignment changes. Expired required documents prevent new rides. Earnings, support and renewals remain available.")
        OutlinedButton(enabled=!busy,onClick={scope.launch{refresh()}}){Text(if(busy) "Refreshing…" else "Refresh")}
        error?.let{Text(it,color=MaterialTheme.colorScheme.error)}
        if(messages.isEmpty()&&!busy)Text("No updates yet.")
        messages.forEach{m->Card(Modifier.fillMaxWidth()){Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text(m.optString("kind").replace('_',' '),style=MaterialTheme.typography.titleSmall);Text(m.optString("message"))
            Text(java.text.DateFormat.getDateTimeInstance().format(java.util.Date(m.optLong("createdAtEpochMs"))),style=MaterialTheme.typography.bodySmall)
            if(m.isNull("readAtEpochMs"))TextButton(onClick={scope.launch{try{api.json("POST","v3/operations/driver/inbox",JSONObject().put("ids",JSONArray().put(m.getString("id"))));refresh()}catch(e:Exception){error=e.message}}}){Text("Mark read")}
        }}}
    }
}
@Composable
internal fun PickupCheckIn44(rideId:String){
    val context=LocalContext.current
    val api=remember {DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL,FleetCredentials(context).load(),true)}
    val scope=rememberCoroutineScope()
    var state by remember(rideId){mutableStateOf("NONE")}
    var message by remember{mutableStateOf<String?>(null)}
    var busy by remember{mutableStateOf(false)}
    LaunchedEffect(rideId){while(true){try{state=api.json("GET","v3/operations/driver/rides/$rideId/check-in").optString("state")}catch(e:CancellationException){throw e}catch(_:Exception){message="Check-in status unavailable. Reconnect to refresh."};delay(10_000)}}
    if(state in setOf("CHECK_IN","ACKNOWLEDGED","ESCALATED"))Card(Modifier.fillMaxWidth()){Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
        Text("Is everything OK?",style=MaterialTheme.typography.titleMedium)
        Text("Pickup is taking longer. Respond only when safely stopped. Road conditions and GPS errors happen; this alert does not affect earnings.")
        if(state=="ACKNOWLEDGED")Text("Response received. We’ll check progress again after a few minutes.")
        listOf("TRAFFIC" to "Traffic delay","ROAD_CLOSED" to "Road closed","NAVIGATION" to "Finding pickup","UNABLE" to "Cannot reach pickup","NEED_HELP" to "Need assistance").forEach{(value,label)->OutlinedButton(enabled=!busy,onClick={scope.launch{busy=true;try{state=api.json("POST","v3/operations/driver/rides/$rideId/check-in",JSONObject().put("reason",value)).getString("state");message="Response sent to operations."}catch(e:Exception){message=e.message}finally{busy=false}}}){Text(label)}}
        message?.let{Text(it)};Text("This is not an emergency response service. In immediate danger, stop safely and call 911.",style=MaterialTheme.typography.bodySmall)
    }}
}
internal suspend fun saveRoute44(context:android.content.Context,rideId:String,route:RoadRoute,trip:Boolean){
    val token=FleetCredentials(context).load();if(token.isBlank()||route.points.size<2)return
    val points=JSONArray();val count=minOf(300,route.points.size)
    for(i in 0 until count){val p=route.points[i*route.points.lastIndex/(count-1)];points.put(JSONObject().put("latitude",p.latitude).put("longitude",p.longitude))}
    try{DriverHttpApi(BuildConfig.RIDENOVA_DEV_URL,token,true).json("POST","v3/operations/driver/rides/$rideId/route",JSONObject().put("leg",if(trip) "TRIP" else "PICKUP").put("points",points).put("durationSeconds",route.etaMinutes*60).put("distanceMeters",route.distanceMeters))}catch(e:CancellationException){throw e}catch(_:Exception){/* Next route refresh retries without blocking navigation. */}
}
