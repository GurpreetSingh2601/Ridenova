package com.ridenova.driver.data

import android.content.Context
import com.ridenova.driver.model.DriverProfile

/** Local demo identity; future verified profiles must come from the server. */
class DriverProfileStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("driver_demo_profile", Context.MODE_PRIVATE)

    fun load() = DriverProfile(
        name = prefs.getString("name", "Driver") ?: "Driver",
        vehicle = prefs.getString("vehicle", "Add your vehicle") ?: "Add your vehicle",
        plate = prefs.getString("plate", "Not set") ?: "Not set"
    )

    fun save(profile: DriverProfile) {
        prefs.edit().putString("name", profile.name.trim())
            .putString("vehicle", profile.vehicle.trim()).putString("plate", profile.plate.trim()).apply()
    }
}
