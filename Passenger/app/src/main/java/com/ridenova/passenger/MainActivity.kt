package com.ridenova.passenger

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import com.google.android.libraries.places.api.Places
import com.ridenova.passenger.ui.RideNovaApp
import com.ridenova.passenger.ui.theme.RideNovaTheme
import com.ridenova.passenger.ui.theme.RideNovaThemeMode

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (BuildConfig.MAPS_API_KEY.isNotBlank() && BuildConfig.MAPS_API_KEY != "YOUR_API_KEY" && !Places.isInitialized()) {
            Places.initializeWithNewPlacesApiEnabled(applicationContext, BuildConfig.MAPS_API_KEY)
        }

        val prefs = getSharedPreferences("ridenova_settings", MODE_PRIVATE)
        val initialMode = runCatching {
            RideNovaThemeMode.valueOf(prefs.getString("theme_mode", RideNovaThemeMode.DARK.name)!!)
        }.getOrDefault(RideNovaThemeMode.DARK)

        setContent {
            var themeMode by remember { mutableStateOf(initialMode) }
            RideNovaTheme(themeMode = themeMode) {
                RideNovaApp(
                    themeMode = themeMode,
                    onThemeModeChange = { newMode ->
                        themeMode = newMode
                        prefs.edit().putString("theme_mode", newMode.name).apply()
                    }
                )
            }
        }
    }
}
