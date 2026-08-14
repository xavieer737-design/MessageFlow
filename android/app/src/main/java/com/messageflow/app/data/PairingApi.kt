package com.messageflow.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * REST client for pairing and heartbeats. OkHttp (the same engine that
 * powers Retrofit) keeps the dependency surface small; JSON via
 * kotlinx.serialization.
 */
class PairingApi(private val client: OkHttpClient = defaultClient()) {

    @Serializable
    data class PairingCompleteRequest(
        val token: String,
        @kotlinx.serialization.SerialName("device_name") val deviceName: String,
        @kotlinx.serialization.SerialName("device_identifier") val deviceIdentifier: String,
        @kotlinx.serialization.SerialName("public_key") val publicKey: String,
        @kotlinx.serialization.SerialName("phone_model") val phoneModel: String? = null,
        @kotlinx.serialization.SerialName("android_version") val androidVersion: String? = null,
        @kotlinx.serialization.SerialName("app_version") val appVersion: String? = null,
    )

    @Serializable
    data class PairingCompleteResponse(
        val device: DeviceDto,
        @kotlinx.serialization.SerialName("device_token") val deviceToken: String,
    )

    @Serializable
    data class DeviceDto(
        val id: Int,
        @kotlinx.serialization.SerialName("device_name") val deviceName: String,
        @kotlinx.serialization.SerialName("phone_model") val phoneModel: String? = null,
        @kotlinx.serialization.SerialName("android_version") val androidVersion: String? = null,
        @kotlinx.serialization.SerialName("connection_status") val connectionStatus: String? = null,
    )

    class ApiException(message: String, val code: Int = 0) : Exception(message)

    /** Redeem a QR pairing token. */
    suspend fun completePairing(
        serverUrl: String,
        request: PairingCompleteRequest,
    ): PairingCompleteResponse = withContext(Dispatchers.IO) {
        val http = Request.Builder()
            .url("$serverUrl/api/devices/pairing/complete")
            .post(Json.encodeToString(PairingCompleteRequest.serializer(), request)
                .toRequestBody(JSON_MEDIA_TYPE))
            .build()
        client.newCall(http).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val detail = runCatching {
                    Json.parseToJsonElement(body).jsonObject["detail"]?.toString()?.trim('"')
                }.getOrNull()
                throw ApiException(detail ?: "Pairing failed (HTTP ${response.code})", response.code)
            }
            Json.decodeFromString(PairingCompleteResponse.serializer(), body)
        }
    }

    @Serializable
    data class HeartbeatRequest(
        @kotlinx.serialization.SerialName("device_identifier") val deviceIdentifier: String,
        @kotlinx.serialization.SerialName("battery_level") val batteryLevel: Int? = null,
        @kotlinx.serialization.SerialName("sim_state") val simState: String? = null,
        @kotlinx.serialization.SerialName("network_state") val networkState: String? = null,
        @kotlinx.serialization.SerialName("app_version") val appVersion: String? = null,
    )

    /** REST heartbeat fallback (the WebSocket heartbeat is primary). */
    suspend fun heartbeat(
        serverUrl: String,
        deviceId: Int,
        deviceIdentifier: String,
        batteryLevel: Int?,
        simState: String?,
        networkState: String?,
        appVersion: String?,
    ): Boolean = withContext(Dispatchers.IO) {
        val payload = HeartbeatRequest(
            deviceIdentifier = deviceIdentifier,
            batteryLevel = batteryLevel,
            simState = simState,
            networkState = networkState,
            appVersion = appVersion,
        )
        val http = Request.Builder()
            .url("$serverUrl/api/devices/$deviceId/heartbeat")
            .post(Json.encodeToString(HeartbeatRequest.serializer(), payload).toRequestBody(JSON_MEDIA_TYPE))
            .build()
        runCatching {
            client.newCall(http).execute().use { it.isSuccessful }
        }.getOrDefault(false)
    }

    companion object {
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .build()
    }
}
