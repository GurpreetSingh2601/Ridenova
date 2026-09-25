package com.ridenova.driver.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF111111),
    onPrimary = Color.White,
    secondary = Color(0xFF2878FF),
    background = Color(0xFFF7F7F7),
    surface = Color.White,
    onSurface = Color(0xFF171717)
)

private val DarkColors = darkColorScheme(
    primary = Color.White,
    onPrimary = Color.Black,
    secondary = Color(0xFF73A7FF),
    background = Color(0xFF090B0D),
    surface = Color(0xFF15181C),
    surfaceVariant = Color(0xFF23282E),
    onSurface = Color(0xFFF4F5F7),
    onSurfaceVariant = Color(0xFFB5BEC8),
    primaryContainer = Color(0xFF28313B),
    onPrimaryContainer = Color(0xFFE4EDFA),
    outline = Color(0xFF76818E)
)

@Composable
fun RideNovaDriverTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        typography = Typography(),
        content = content
    )
}
