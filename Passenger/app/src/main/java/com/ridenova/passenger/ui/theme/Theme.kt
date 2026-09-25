package com.ridenova.passenger.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

enum class RideNovaThemeMode {
    SYSTEM,
    LIGHT,
    DARK
}

val LocalRideNovaDarkTheme = staticCompositionLocalOf { false }

private val RideNovaTypography = Typography(
    displayLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.8f).sp),
    headlineLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.45f).sp),
    headlineMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.3f).sp),
    titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.2f).sp),
    titleMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Medium, letterSpacing = (-0.1f).sp),
    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, letterSpacing = 0.sp),
    bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, letterSpacing = 0.sp),
    labelLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Medium, letterSpacing = 0.sp)
)

private val RideNovaLightColors = lightColorScheme(
    primary = NovaMidnight,
    onPrimary = Color.White,
    secondary = NovaBlue,
    tertiary = NovaViolet,
    background = NovaIce,
    surface = Color.White,
    surfaceVariant = Color(0xFFF0F3F9),
    onSurface = NovaInk,
    onSurfaceVariant = NovaMuted,
    onBackground = NovaInk,
    outline = Color(0xFFD4DAE5)
)

private val RideNovaDarkColors = darkColorScheme(
    primary = Color(0xFF91A4FF),
    onPrimary = Color(0xFF07101F),
    secondary = Color(0xFF9A8CFF),
    tertiary = Color(0xFFB59BFF),
    background = Color(0xFF07090D),
    surface = Color(0xFF111318),
    surfaceVariant = Color(0xFF1B1E25),
    onSurface = Color(0xFFF5F7FB),
    onSurfaceVariant = Color(0xFFB1B8C5),
    onBackground = Color(0xFFF5F7FB),
    outline = Color(0xFF3B414D)
)

@Composable
fun RideNovaTheme(
    themeMode: RideNovaThemeMode = RideNovaThemeMode.SYSTEM,
    content: @Composable () -> Unit
) {
    val darkTheme = when (themeMode) {
        RideNovaThemeMode.SYSTEM -> isSystemInDarkTheme()
        RideNovaThemeMode.LIGHT -> false
        RideNovaThemeMode.DARK -> true
    }

    CompositionLocalProvider(LocalRideNovaDarkTheme provides darkTheme) {
        MaterialTheme(
            colorScheme = if (darkTheme) RideNovaDarkColors else RideNovaLightColors,
            typography = RideNovaTypography,
            content = content
        )
    }
}
