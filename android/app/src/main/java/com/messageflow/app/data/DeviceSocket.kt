package com.messageflow.app.data

import com.messageflow.app.data.protocol.ProtocolJson
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.TimeUnit

/**
 * WebSocket connection to the MessageFlow backend with:
 *  - challenge/response auth (nonce signed with the Keystore key),
 *  - automatic reconnect with exponential backoff + jitter,
 *  - heartbeat while connected,
 *  - raw incoming messages forwarded to [messages] for the service.
 */
class DeviceSocket(
    private val identity: KeystoreIdentity,
    private val appVersion: String,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .build(),
) {
    sealed interface State {
        data object Disconnected : State
        data object Connecting : State
        data object Authenticating : State
        data object Connected : State
    }

    private val _state = MutableSharedFlow<State>(extraBufferCapacity = 8)
    val state: SharedFlow<State> = _state

    private val _messages = MutableSharedFlow<JsonObject>(extraBufferCapacity = 64)
    val messages: SharedFlow<JsonObject> = _messages

    private var webSocket: WebSocket? = null
    private var reconnectJob: Job? = null
    private var heartbeatJob: Job? = null
    private var scope: CoroutineScope? = null
    private var serverUrl: String = ""
    private var deviceId: Int = 0
    private var token: String = ""
    private var running = false
    private var connected = false

    fun start(scope: CoroutineScope, serverUrl: String, deviceId: Int, token: String) {
        this.scope = scope
        this.serverUrl = serverUrl
        this.deviceId = deviceId
        this.token = token
        this.running = true
        connectWithBackoff(attempt = 0)
    }

    fun stop() {
        running = false
        reconnectJob?.cancel()
        heartbeatJob?.cancel()
        webSocket?.close(1000, "app stopped")
        webSocket = null
        _state.tryEmit(State.Disconnected)
    }

    fun send(json: String) {
        webSocket?.send(json)
    }

    private fun connectWithBackoff(attempt: Int) {
        if (!running) return
        _state.tryEmit(State.Connecting)
        val wsUrl = serverUrl
            .replaceFirst("https://", "wss://")
            .replaceFirst("http://", "ws://")
            .trimEnd('/') + "/api/devices/ws"

        val request = Request.Builder().url(wsUrl).build()
        webSocket = client.newWebSocket(request, listener(attempt))
    }

    private fun listener(attempt: Int) = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            _state.tryEmit(State.Authenticating)
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            val json = runCatching { Json.parseToJsonElement(text).jsonObject }.getOrNull()
                ?: return
            val type = json["type"]?.toString()?.trim('"') ?: return

            when (type) {
                "challenge" -> {
                    val nonce = json["nonce"]?.toString()?.trim('"') ?: return
                    val signature = identity.sign(nonce)
                    val auth = ProtocolJson.json.encodeToString(
                        com.messageflow.app.data.protocol.AuthMessage.serializer(),
                        com.messageflow.app.data.protocol.AuthMessage(
                            deviceId = deviceId,
                            token = token,
                            signature = signature,
                        ),
                    )
                    webSocket.send(auth)
                }
                "welcome" -> {
                    connected = true
                    _state.tryEmit(State.Connected)
                    startHeartbeat()
                }
                "ping" -> webSocket.send("""{"type":"pong"}""")
            }
            _messages.tryEmit(json)
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            connected = false
            _state.tryEmit(State.Disconnected)
            scheduleReconnect(attempt)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            connected = false
            _state.tryEmit(State.Disconnected)
            scheduleReconnect(attempt)
        }
    }

    private fun scheduleReconnect(attempt: Int) {
        if (!running) return
        reconnectJob?.cancel()
        val scope = this.scope ?: return
        reconnectJob = scope.launch {
            // Exponential backoff with jitter: 1s, 2s, 4s, ... max 60s.
            val backoff = minOf(60_000L, 1_000L shl minOf(attempt, 6))
            val jitter = (Math.random() * backoff * 0.3).toLong()
            delay(backoff + jitter)
            if (running) connectWithBackoff(attempt + 1)
        }
    }

    private fun startHeartbeat() {
        heartbeatJob?.cancel()
        val scope = this.scope ?: return
        heartbeatJob = scope.launch {
            while (running) {
                delay(HEARTBEAT_INTERVAL_MS)
                if (!connected) continue
                val heartbeat = ProtocolJson.json.encodeToString(
                    com.messageflow.app.data.protocol.HeartbeatMessage.serializer(),
                    com.messageflow.app.data.protocol.HeartbeatMessage(
                        batteryLevel = batteryProvider?.invoke(),
                        simState = simProvider?.invoke(),
                        networkState = networkProvider?.invoke(),
                        appVersion = appVersion,
                    ),
                )
                webSocket?.send(heartbeat)
            }
        }
    }

    /** Optional telemetry providers (injected by the service with Context). */
    var batteryProvider: (() -> Int?)? = null
    var simProvider: (() -> String?)? = null
    var networkProvider: (() -> String?)? = null

    companion object {
        const val HEARTBEAT_INTERVAL_MS = 30_000L
    }
}
