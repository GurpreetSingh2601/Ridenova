package com.ridenova.driver.location

import android.content.Context
import com.ridenova.driver.data.DriverApiException
import com.ridenova.driver.data.DriverHttpApi
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest

/** Bounded app-private recovery buffer, scoped to the signed-in credential and original trip. */
internal class TripGpsQueue44(context:Context,token:String){
    private val prefs=context.getSharedPreferences("gps_queue44",Context.MODE_PRIVATE)
    private val key=MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString(""){"%02x".format(it)}
    init { if(prefs.getString("credential", null)!=key) prefs.edit().clear().putString("credential",key).apply() }
    private fun read():MutableList<JSONObject> = runCatching{val a=JSONArray(prefs.getString(key,"[]"));(0 until a.length()).map{a.getJSONObject(it)}.toMutableList()}.getOrDefault(mutableListOf())
    private fun save(items:List<JSONObject>){prefs.edit().putString(key,JSONArray(items).toString()).apply()}
    @Synchronized fun add(p:JSONObject){val items=read();items.add(p);save(items.filter{System.currentTimeMillis()-it.optLong("observedAtEpochMs")<86400000}.takeLast(900))}
    suspend fun flush(api:DriverHttpApi){repeat(20){val first=synchronized(this){read().firstOrNull()}?:return
        try{api.json("POST","v2/fleet/driver/location",first)}catch(e:DriverApiException){if(e.status !in setOf(400,403,404,409))throw e}
        synchronized(this){val items=read();if(items.firstOrNull()?.toString()==first.toString())items.removeAt(0);save(items)}
    }}
}
