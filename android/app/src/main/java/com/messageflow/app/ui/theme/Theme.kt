package com.messageflow.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// MessageFlow brand palette (indigo, mirrors the web dashboard).
val Brand600 = Color(0xFF4F46E5)
val Brand700 = Color(0xFF4338CA)
val Zinc900 = Color(0xFF18181B)
val Zinc50 = Color(0xFFFAFAFA)

private val LightColors = lightColorScheme(
    primary = Brand600,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE0E7FF),
    onPrimaryContainer = Brand700,
    secondary = Color(0xFF52525B),
    background = Zinc50,
    surface = Color.White,
    onBackground = Zinc900,
    onSurface = Zinc900,
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF818CF8),
    onPrimary = Color(0xFF1E1B4B),
    primaryContainer = Color(0xFF3730A3),
    onPrimaryContainer = Color(0xFFE0E7FF),
    secondary = Color(0xFFA1A1AA),
    background = Color(0xFF09090B),
    surface = Color(0xFF18181B),
    onBackground = Color(0xFFF4F4F5),
    onSurface = Color(0xFFF4F4F5),
)

@Composable
fun MessageFlowTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
