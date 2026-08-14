package com.messageflow.app.data

import android.content.Context
import android.net.ConnectivityManager
import android.os.BatteryManager
import android.os.Build
import android.telephony.TelephonyManager

/**
 * Best-effort telemetry reported in heartbeats. Every accessor is
 * wrapped so a failure never breaks the heartbeat loop; values are
 * only what the device can actually report (nothing fabricated).
 */
object DeviceInfo {

    fun batteryLevelPercent(context: Context): Int? = runCatching {
        val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val level = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        if (level in 0..100) level else null
    }.getOrNull()

    fun simState(context: Context): String? = runCatching {
        val telephony = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
        when (telephony.simState) {
            TelephonyManager.SIM_STATE_READY -> "READY"
            TelephonyManager.SIM_STATE_ABSENT -> "ABSENT"
            TelephonyManager.SIM_STATE_PIN_REQUIRED -> "PIN_REQUIRED"
            TelephonyManager.SIM_STATE_PUK_REQUIRED -> "PUK_REQUIRED"
            TelephonyManager.SIM_STATE_NETWORK_LOCKED -> "NETWORK_LOCKED"
            TelephonyManager.SIM_STATE_NOT_READY -> "NOT_READY"
            TelephonyManager.SIM_STATE_PERM_DISABLED -> "PERM_DISABLED"
            TelephonyManager.SIM_STATE_CARD_IO_ERROR -> "CARD_IO_ERROR"
            else -> "UNKNOWN"
        }
    }.getOrNull()

    fun networkState(context: Context): String? = runCatching {
        val connectivity = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val active = connectivity.activeNetwork ?: return@runCatching "NONE"
        val capabilities = connectivity.getNetworkCapabilities(active) ?: return@runCatching "UNKNOWN"
        when {
            capabilities.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI) -> "WIFI"
            capabilities.hasTransport(android.net.NetworkCapabilities.TRANSPORT_CELLULAR) -> "MOBILE"
            capabilities.hasTransport(android.net.NetworkCapabilities.TRANSPORT_ETHERNET) -> "ETHERNET"
            else -> "OTHER"
        }
    }.getOrNull()

    fun androidVersion(): String = Build.VERSION.RELEASE

    fun phoneModel(): String = "${Build.MANUFACTURER} ${Build.MODEL}".trim()
}
