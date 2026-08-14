package com.messageflow.app.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

/**
 * Persisted app state: pairing info, device token and the idempotency
 * result store. Values are encrypted at rest via Android Keystore-backed
 * AES (EncryptedStorage).
 */
private val Context.dataStore by preferencesDataStore(name = "messageflow")

/** Idempotency result store abstraction (implemented by AppStorage). */
interface ResultStore {
    suspend fun saveResult(messageId: String, resultJson: String)
    suspend fun findResult(messageId: String): String?
    suspend fun clearResults()
}

class AppStorage(private val context: Context) : ResultStore {

    private val encrypted = EncryptedStorage(context)

    // Raw preferences (non-secret).
    val serverUrl: Flow<String?> = context.dataStore.data.map { it[SERVER_URL] }
    val deviceId: Flow<Int?> = context.dataStore.data.map { it[DEVICE_ID] }
    val paired: Flow<Boolean> = context.dataStore.data.map { it[PAIRED] ?: false }
    val receiveSmsEnabled: Flow<Boolean> = context.dataStore.data.map { it[RECEIVE_SMS_OPT_IN] ?: false }
    val deviceIdentifier: Flow<String?> = context.dataStore.data.map { it[DEVICE_IDENTIFIER] }

    suspend fun saveServerUrl(url: String) {
        context.dataStore.edit { it[SERVER_URL] = url }
    }

    suspend fun saveDeviceIdentifier(identifier: String) {
        context.dataStore.edit { it[DEVICE_IDENTIFIER] = identifier }
    }

    suspend fun savePairing(deviceId: Int, deviceName: String, token: String) {
        context.dataStore.edit {
            it[DEVICE_ID] = deviceId
            it[PAIRED] = true
            it[DEVICE_NAME] = deviceName
        }
        encrypted.write("device_token", token)
    }

    suspend fun saveDeviceName(name: String) {
        context.dataStore.edit { it[DEVICE_NAME] = name }
    }

    suspend fun deviceName(): String = context.dataStore.data.map { it[DEVICE_NAME] }.first() ?: "Android device"

    suspend fun deviceToken(): String? = encrypted.read("device_token")

    suspend fun setReceiveSmsOptIn(enabled: Boolean) {
        context.dataStore.edit { it[RECEIVE_SMS_OPT_IN] = enabled }
    }

    suspend fun clearPairing() {
        context.dataStore.edit {
            it[DEVICE_ID] = null
            it[PAIRED] = false
            it[DEVICE_NAME] = null
        }
        encrypted.delete("device_token")
    }

    // --- Idempotency store: message_id -> result ---
    // Kept small (bounded), encrypted; used to avoid double-sending when
    // the server retries a command after a reconnect.

    override suspend fun saveResult(messageId: String, resultJson: String) {
        val existing = results()
        val updated = (existing + (messageId to resultJson)).takeLast(MAX_RESULTS)
        encrypted.write("results", updated.joinToString("\u0001") { "${it.key}\u0002${it.value}" })
    }

    override suspend fun findResult(messageId: String): String? = results()[messageId]

    override suspend fun clearResults() = encrypted.delete("results")

    private suspend fun results(): Map<String, String> {
        val raw = encrypted.read("results") ?: return emptyMap()
        return raw.split("\u0001")
            .filter { it.contains("\u0002") }
            .mapNotNull {
                val parts = it.split("\u0002", limit = 2)
                if (parts.size == 2) parts[0] to parts[1] else null
            }
            .toMap()
    }

    private companion object {
        val SERVER_URL = stringPreferencesKey("server_url")
        val DEVICE_ID = intPreferencesKey("device_id")
        val DEVICE_IDENTIFIER = stringPreferencesKey("device_identifier")
        val DEVICE_NAME = stringPreferencesKey("device_name")
        val PAIRED = booleanPreferencesKey("paired")
        val RECEIVE_SMS_OPT_IN = booleanPreferencesKey("receive_sms_opt_in")
        const val MAX_RESULTS = 500
    }
}
