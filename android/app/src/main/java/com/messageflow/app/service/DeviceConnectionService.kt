package com.messageflow.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.messageflow.app.MainActivity
import com.messageflow.app.R
import com.messageflow.app.data.AndroidSmsSender
import com.messageflow.app.data.AppStorage
import com.messageflow.app.data.DeviceInfo
import com.messageflow.app.data.DeviceSocket
import com.messageflow.app.data.KeystoreIdentity
import com.messageflow.app.data.SendCommandProcessor
import com.messageflow.app.data.protocol.IncomingSmsMessage
import com.messageflow.app.data.protocol.MessageResultMessage
import com.messageflow.app.data.protocol.ProtocolJson
import com.messageflow.app.data.protocol.SendMessageCommand
import com.messageflow.app.receiver.DeviceConnectionServiceBridge
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject

/**
 * Foreground service owning the device's connection to the backend.
 *
 * Responsibilities:
 *  - hold the WebSocket (with reconnect/backoff) while the app runs,
 *  - authenticate with the Keystore-signed challenge response,
 *  - forward send_message commands to [SendCommandProcessor] one at a
 *    time (server-controlled queueing; nothing is stored long-term),
 *  - send real SmsManager results back as message_result,
 *  - forward incoming SMS for STOP handling when opted in,
 *  - report heartbeats with real telemetry.
 */
class DeviceConnectionService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var storage: AppStorage
    private lateinit var socket: DeviceSocket
    private lateinit var processor: SendCommandProcessor

    init {
        // Reset the shared state whenever the service (re)starts.
        connectionState.value = DeviceSocket.State.Connecting
    }

    // Commands are executed sequentially (one SMS at a time) on their own
    // channel so heartbeats and control messages stay responsive.
    private val commandChannel = Channel<SendMessageCommand>(Channel.UNLIMITED)

    override fun onCreate() {
        super.onCreate()
        storage = AppStorage(this)
        createNotificationChannel()

        val smsSender = AndroidSmsSender(this)
        processor = SendCommandProcessor(storage, smsSender)
        socket = DeviceSocket(KeystoreIdentity, BuildConfig.VERSION_NAME)

        socket.batteryProvider = { DeviceInfo.batteryLevelPercent(this) }
        socket.simProvider = { DeviceInfo.simState(this) }
        socket.networkProvider = { DeviceInfo.networkState(this) }

        // Keep the shared connection state in sync for the UI.
        scope.launch {
            socket.state.collect { state ->
                connectionState.value = state
                updateNotification(
                    when (state) {
                        DeviceSocket.State.Connected -> "Connected to dashboard"
                        DeviceSocket.State.Authenticating -> "Authenticating…"
                        DeviceSocket.State.Connecting -> "Connecting…"
                        DeviceSocket.State.Disconnected -> "Offline - reconnecting"
                    }
                )
            }
        }

        startForeground(NOTIFICATION_ID, buildNotification("Connecting…"))

        scope.launch {
            val serverUrl = storage.serverUrl.first() ?: return@launch
            val deviceId = storage.deviceId.first() ?: return@launch
            val token = storage.deviceToken() ?: return@launch
            socket.start(scope, serverUrl, deviceId, token)

            // Sequential command executor.
            launch {
                for (command in commandChannel) {
                    val result = processor.handle(command)
                    socket.send(
                        ProtocolJson.json.encodeToString(
                            MessageResultMessage.serializer(),
                            MessageResultMessage(
                                messageId = result.messageId,
                                status = result.status,
                                error = result.error,
                                timestamp = result.timestamp,
                            ),
                        )
                    )
                    updateNotification("Last send: ${result.status}")
                }
            }

            // Incoming messages from the socket.
            launch {
                socket.messages.collect { json -> processIncoming(json) }
            }

            // Bridge for optional STOP handling from incoming SMS.
            DeviceConnectionServiceBridge.forwardIncomingSms = { _, sender, body ->
                scope.launch {
                    if (hasReceiveSmsOptIn()) {
                        socket.send(
                            ProtocolJson.json.encodeToString(
                                IncomingSmsMessage.serializer(),
                                IncomingSmsMessage(sender = sender, body = body),
                            )
                        )
                    }
                }
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onDestroy() {
        DeviceConnectionServiceBridge.forwardIncomingSms = null
        socket.stop()
        scope.cancel()
        connectionState.value = DeviceSocket.State.Disconnected
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun processIncoming(json: JsonObject) {
        val type = json["type"]?.toString()?.trim('"') ?: return
        when (type) {
            "send_message" -> {
                val command = runCatching {
                    ProtocolJson.json.decodeFromString(
                        SendMessageCommand.serializer(),
                        json.toString(),
                    )
                }.getOrNull() ?: return
                if (!hasSmsPermission()) {
                    socket.send(
                        ProtocolJson.json.encodeToString(
                            MessageResultMessage.serializer(),
                            MessageResultMessage(
                                messageId = command.messageId,
                                status = "SEND_FAILED",
                                error = "SMS permission not granted",
                            ),
                        )
                    )
                    return
                }
                commandChannel.trySend(command)
            }
            "pause" -> processor.pause()
            "resume" -> processor.resume()
            "cancel" -> processor.cancel()
            "disconnect" -> {
                socket.stop()
                stopSelf()
            }
        }
    }

    private fun hasSmsPermission(): Boolean =
        checkSelfPermission(android.Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED

    private suspend fun hasReceiveSmsOptIn(): Boolean =
        checkSelfPermission(android.Manifest.permission.RECEIVE_SMS) == PackageManager.PERMISSION_GRANTED &&
            storage.receiveSmsEnabled.first()

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID, "Device connection",
            NotificationManager.IMPORTANCE_LOW,
        )
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        val contentIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("MessageFlow")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_stat_messageflow)
            .setContentIntent(contentIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, buildNotification(text))
    }

    companion object {
        private const val CHANNEL_ID = "device_connection"
        private const val NOTIFICATION_ID = 42

        /** Live connection state shared with the UI (polled by AppViewModel). */
        val connectionState = kotlinx.coroutines.flow.MutableStateFlow<DeviceSocket.State>(
            DeviceSocket.State.Disconnected
        )

        fun start(context: Context) {
            val intent = Intent(context, DeviceConnectionService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }
    }
}
