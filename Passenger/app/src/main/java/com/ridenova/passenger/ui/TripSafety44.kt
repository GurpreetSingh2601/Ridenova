package com.ridenova.passenger.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Looper
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
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.google.android.gms.location.*
import com.ridenova.passenger.BuildConfig
import com.ridenova.passenger.data.ApiResult
import com.ridenova.passenger.data.RideNovaHttpClient
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.json.JSONObject

@Composable
internal fun TripSafety44(rideId:String,client:RideNovaHttpClient){
    val context=LocalContext.current
    val scope=rememberCoroutineScope()
    val lifecycle=LocalLifecycleOwner.current.lifecycle
    val fused=remember{LocationServices.getFusedLocationProviderClient(context)}
    var open by remember{mutableStateOf(false)}
    var enabled by remember(rideId){mutableStateOf(false)}
    var foreground by remember{mutableStateOf(lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED))}
    var message by remember{mutableStateOf<String?>(null)}
    var busy by remember{mutableStateOf(false)}
    val prefs=remember{context.getSharedPreferences("ridenova_safety44",android.content.Context.MODE_PRIVATE)}
    var contact by remember{mutableStateOf(prefs.getString("contact","").orEmpty())}
    val base="v3/operations/passenger/rides/$rideId/"
    suspend fun send(action:String,body:JSONObject):JSONObject=when(val r=client.post(base+action,body)){is ApiResult.Success->r.value;is ApiResult.Failure->error(r.message)}
    fun consent(value:Boolean){scope.launch{busy=true;try{enabled=send("consent",JSONObject().put("enabled",value)).getBoolean("enabled");message=if(value) "Sharing while this trip screen is open." else "Sharing stopped; passenger location samples removed."}catch(e:CancellationException){throw e}catch(e:Exception){message=e.message}finally{busy=false}}}
    val permission=rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()){r->if(r.values.any{it})consent(true) else message="Location permission not granted. You can still share the driver’s trip link."}
    DisposableEffect(lifecycle){val observer=LifecycleEventObserver{_,_->foreground=lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)};lifecycle.addObserver(observer);onDispose{lifecycle.removeObserver(observer)}}
    LaunchedEffect(rideId){when(val r=client.get(base+"consent")){is ApiResult.Success->enabled=r.value.optBoolean("enabled");is ApiResult.Failure->message=r.message}}
    DisposableEffect(enabled,foreground,rideId){
        var sending=false
        val callback=object:LocationCallback(){override fun onLocationResult(result:LocationResult){val p=result.lastLocation?:return;if(sending)return;sending=true;scope.launch{try{send("location",JSONObject().put("latitude",p.latitude).put("longitude",p.longitude).put("accuracyMeters",p.accuracy.toDouble()).put("observedAtEpochMs",p.time))}catch(e:CancellationException){throw e}catch(_:Exception){message="Location update failed. Next fresh sample will retry."}finally{sending=false}}}}
        val allowed=ContextCompat.checkSelfPermission(context,Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED||ContextCompat.checkSelfPermission(context,Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED
        if(enabled&&foreground&&allowed)try{fused.requestLocationUpdates(LocationRequest.Builder(Priority.PRIORITY_BALANCED_POWER_ACCURACY,10_000).build(),callback,Looper.getMainLooper())}catch(_:SecurityException){message="Location permission required."}
        onDispose{fused.removeLocationUpdates(callback)}
    }
    OutlinedButton(onClick={open=true},modifier=Modifier.fillMaxWidth()){Text(if(enabled) "Safety · location sharing on" else "Safety & share trip")}
    if(open)AlertDialog(onDismissRequest={open=false},title={Text("Trip safety")},text={Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(10.dp)){
        Text("Share an expiring link with your driver’s latest location and destination. Anyone with the link can view it until revoked or the trip ends.")
        Button(enabled=!busy,onClick={scope.launch{busy=true;try{val r=send("share",JSONObject().put("action","create"));val url=BuildConfig.RIDENOVA_API_BASE_URL.trimEnd('/')+"/share#"+r.getString("token");context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT,"Follow my RideNova trip: $url"),"Share trip"))}catch(e:Exception){message=e.message}finally{busy=false}}}){Text("Create sharing link")}
        TextButton(enabled=!busy,onClick={scope.launch{try{send("share",JSONObject().put("action","revoke"));message="Previous links are inactive."}catch(e:Exception){message=e.message}}}){Text("Revoke sharing links")}
        Text("Optionally share this phone’s GPS with authorized RideNova operations staff. Only while this trip screen is open; no off-trip tracking. Turning off removes passenger GPS samples.")
        Row{Switch(checked=enabled,enabled=!busy,onCheckedChange={v->if(!v)consent(false) else permission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION))});Text("Share my location",Modifier.padding(8.dp))}
        OutlinedTextField(value=contact,onValueChange={if(it.length<=30)contact=it},label={Text("Emergency contact phone")},singleLine=true)
        TextButton(onClick={prefs.edit().putString("contact",contact.trim()).apply();message="Contact saved on this phone only."}){Text("Save contact")}
        OutlinedButton(enabled=contact.isNotBlank(),onClick={context.startActivity(Intent(Intent.ACTION_DIAL,Uri.fromParts("tel",contact,null)))}){Text("Call contact")}
        OutlinedButton(onClick={context.startActivity(Intent(Intent.ACTION_DIAL,Uri.parse("tel:911")))}){Text("Emergency · dial 911")}
        Text("RideNova alerts are not an emergency response service.")
        message?.let{Text(it)}
    }},confirmButton={TextButton(onClick={open=false}){Text("Done")}})
}
