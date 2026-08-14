package com.messageflow.app.viewmodel

import android.app.Application
import android.content.Context
import android.content.pm.PackageManager
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.messageflow.app.BuildConfig
import com.messageflow.app.data.AppStorage
import com.messageflow.app.data.DeviceInfo
import com.messageflow.app.data.DeviceSocket
import com.messageflow.app.data.KeystoreIdentity
import com.messageflow.app.data.PairingApi
import com.messageflow.app.data.QrPayloadParser
import com.messageflow.app.service.DeviceConnectionService
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

data class AppUiState(
    val paired: Boolean = false,
    val pairing: PairingPhase = PairingPhase.Idle,
    val connectionLabel: String = "Disconnected",
    val deviceName: String = "",
    val phoneModel: String = "",
    val androidVersion: String = "",
    val batteryLevel: Int? = null,
    val simState: String? = null,
    val networkState: String? = null,
    val hasSmsPermission: Boolean = false,
    val hasReceiveSmsPermission: Boolean = false,
    val receiveSmsOptIn: Boolean = false,
    val deviceIdentifier: String = "",
    val serverUrl: String = "",
    val pairingError: String? = null,
    val lastSync: String? = null,
)

enum class PairingPhase {
    Idle, Completing, Success, Error
}

class AppViewModel(application: Application) : AndroidViewModel(application) {

    private val storage = AppStorage(application)
    private val api = PairingApi()

    private val _appState = MutableStateFlow(AppUiState())
    val appState: StateFlow<AppUiState> = _appState

    private var connectionState: DeviceSocket.State = DeviceSocket.State.Disconnected

    init {
        viewModelScope.launch {
            // Poll storage + telemetry for a simple, robust UI state.
            while (true) {
                refreshState()
                delay(5_000)
            }
        }
    }

    private suspend fun refreshState() {
        val ctx = getApplication<Application>()
        connectionState = DeviceConnectionService.connectionState.value
        _appState.value = AppUiState(
            paired = storage.paired.first(),
            pairing = _appState.value.pairing,
            connectionLabel = when (connectionState) {
                DeviceSocket.State.Connected -> "CONNECTED"
                DeviceSocket.State.Authenticating -> "AUTHENTICATING"
                DeviceSocket.State.Connecting -> "CONNECTING"
                DeviceSocket.State.Disconnected -> "OFFLINE"
            },
            deviceName = storage.deviceName(),
            phoneModel = DeviceInfo.phoneModel(),
            androidVersion = DeviceInfo.androidVersion(),
            batteryLevel = DeviceInfo.batteryLevelPercent(ctx),
            simState = DeviceInfo.simState(ctx),
            networkState = DeviceInfo.networkState(ctx),
            hasSmsPermission = hasPermission(android.Manifest.permission.SEND_SMS),
            hasReceiveSmsPermission = hasPermission(android.Manifest.permission.RECEIVE_SMS),
            receiveSmsOptIn = storage.receiveSmsEnabled.first(),
            deviceIdentifier = storage.deviceIdentifier.first() ?: "",
            serverUrl = storage.serverUrl.first() ?: "",
            pairingError = _appState.value.pairingError,
            lastSync = _appState.value.lastSync,
        )
    }


    /** Step 1 of pairing: parse the scanned QR payload. */
    fun onQrScanned(raw: String) {
        viewModelScope.launch {
            _appState.value = _appState.value.copy(pairing = PairingPhase.Completing, pairingError = null)
            try {
                val payload = QrPayloadParser.parse(raw)
                val serverUrl = payload["server"] ?: throw IllegalArgumentException("QR payload missing server")
                val token = payload["token"] ?: throw IllegalArgumentException("QR payload missing token")

                val identifier = storage.deviceIdentifier.first()
                    ?: throw IllegalStateException("Device identifier missing - restart the app")

                storage.saveServerUrl(serverUrl)

                val response = api.completePairing(
                    serverUrl,
                    PairingApi.PairingCompleteRequest(
                        token = token,
                        deviceName = "My Android phone",
                        deviceIdentifier = identifier,
                        publicKey = KeystoreIdentity.getPublicKeyPem(),
                        phoneModel = DeviceInfo.phoneModel(),
                        androidVersion = DeviceInfo.androidVersion(),
                        appVersion = BuildConfig.VERSION_NAME,
                    ),
                )

                storage.savePairing(
                    deviceId = response.device.id,
                    deviceName = response.device.deviceName,
                    token = response.deviceToken,
                )
                _appState.value = _appState.value.copy(pairing = PairingPhase.Success)
            } catch (e: Exception) {
                _appState.value = _appState.value.copy(
                    pairing = PairingPhase.Error,
                    pairingError = e.message ?: "Pairing failed",
                )
            }
        }
    }

    fun onPermissionsResult(grants: Map<String, Boolean>) {
        viewModelScope.launch { refreshState() }
    }

    fun toggleReceiveSmsOptIn(enabled: Boolean) {
        viewModelScope.launch { storage.setReceiveSmsOptIn(enabled) }
    }

    fun startDeviceService(context: Context) {
        DeviceConnectionService.start(context)
    }

    fun disconnectDevice() {
        viewModelScope.launch {
            storage.clearPairing()
            _appState.value = AppUiState()
        }
    }

    private fun hasPermission(permission: String): Boolean =
        getApplication<Application>().checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED
}
