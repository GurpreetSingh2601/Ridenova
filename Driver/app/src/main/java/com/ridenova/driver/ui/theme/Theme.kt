package com.ridenova.driver.ui.theme
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
// Shared RideNova visual tokens. Keep Passenger and Driver themes aligned.
private fun type(size: Int, line: Int, weight: FontWeight = FontWeight.Normal) = TextStyle(
    fontFamily = FontFamily.SansSerif, fontSize = size.sp, lineHeight = line.sp, fontWeight = weight, letterSpacing = 0.sp)
private val NovaTypography = Typography(
    displayLarge = type(48,56,FontWeight.Bold), displayMedium = type(40,48,FontWeight.Bold), displaySmall = type(36,44,FontWeight.Bold),
    headlineLarge = type(32,40,FontWeight.Bold), headlineMedium = type(28,36,FontWeight.Bold), headlineSmall = type(24,32,FontWeight.SemiBold),
    titleLarge = type(22,28,FontWeight.SemiBold), titleMedium = type(16,24,FontWeight.SemiBold), titleSmall = type(14,20,FontWeight.SemiBold),
    bodyLarge = type(16,24), bodyMedium = type(14,21), bodySmall = type(12,18),
    labelLarge = type(14,20,FontWeight.SemiBold), labelMedium = type(12,16,FontWeight.Medium), labelSmall = type(11,16,FontWeight.Medium))
private val NovaShapes = Shapes(extraSmall=RoundedCornerShape(8.dp),small=RoundedCornerShape(12.dp),medium=RoundedCornerShape(16.dp),large=RoundedCornerShape(24.dp),extraLarge=RoundedCornerShape(28.dp))
private val LightColors = lightColorScheme(
    primary=Color(0xFF3858D5),onPrimary=Color.White,primaryContainer=Color(0xFFE7ECFF),onPrimaryContainer=Color(0xFF152E80),
    secondary=Color(0xFF3858D5),onSecondary=Color.White,secondaryContainer=Color(0xFFE7ECFF),onSecondaryContainer=Color(0xFF152E80),tertiary=Color(0xFF6F50B6),
    background=Color(0xFFF5F6FA),onBackground=Color(0xFF172033),surface=Color.White,onSurface=Color(0xFF172033),
    surfaceVariant=Color(0xFFEBEEF5),onSurfaceVariant=Color(0xFF536078),outline=Color(0xFF778399),outlineVariant=Color(0xFFDDE2ED))
private val DarkColors = darkColorScheme(
    primary=Color(0xFFA7B6FF),onPrimary=Color(0xFF142458),primaryContainer=Color(0xFF222F53),onPrimaryContainer=Color(0xFFDDE4FF),
    secondary=Color(0xFFA7B6FF),onSecondary=Color(0xFF142458),secondaryContainer=Color(0xFF222F53),onSecondaryContainer=Color(0xFFDDE4FF),tertiary=Color(0xFFCAB5FF),
    background=Color(0xFF0C1018),onBackground=Color(0xFFF3F5FC),surface=Color(0xFF141B27),onSurface=Color(0xFFF3F5FC),
    surfaceVariant=Color(0xFF202A3A),onSurfaceVariant=Color(0xFFB6C0D2),outline=Color(0xFF8793A9),outlineVariant=Color(0xFF334054))

@Composable
fun RideNovaDriverTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme=if(isSystemInDarkTheme()) DarkColors else LightColors,typography=NovaTypography,shapes=NovaShapes,content=content)
}
