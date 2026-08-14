package com.messageflow.app.data.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Wire protocol shared with the MessageFlow backend WebSocket endpoint
 * (/api/devices/ws). Field names and message types must match the
 * backend exactly (backend/app/api/routes/devices_ws.py).
 */

object ProtocolJson {
    val json: Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }
}

// --- Server -> device ---

@Serializable
data class ChallengeMessage(
    val type: String = "challenge",
    val nonce: String,
)

@Serializable
data class WelcomeMessage(
    val type: String = "welcome",
    @SerialName("device_id") val deviceId: Int,
)

@Serializable
data class SendMessageCommand(
    val type: String = "send_message",
    @SerialName("command_id") val commandId: String,
    @SerialName("message_id") val messageId: String,
    @SerialName("idempotency_key") val idempotencyKey: String,
    val phone: String,
    val message: String,
    @SerialName("send_at") val sendAt: String? = null,
    val test: Boolean? = null,
)

@Serializable
data class PauseCommand(val type: String = "pause")

@Serializable
data class ResumeCommand(val type: String = "resume")

@Serializable
data class CancelCommand(val type: String = "cancel")

@Serializable
data class DisconnectCommand(val type: String = "disconnect")

@Serializable
data class PingMessage(val type: String = "ping")

@Serializable
data class ServerError(val type: String = "error", val message: String = "")

@Serializable
data class ResultAck(
    val type: String = "result_ack",
    @SerialName("message_id") val messageId: String,
    val recorded: Boolean,
)

@Serializable
data class HeartbeatAck(val type: String = "heartbeat_ack")

@Serializable
data class IncomingSmsAck(
    val type: String = "incoming_sms_ack",
    val matched: Boolean = false,
    val phone: String? = null,
    val auto_reply: Boolean? = null,
)

// --- Device -> server ---

@Serializable
data class AuthMessage(
    val type: String = "auth",
    @SerialName("device_id") val deviceId: Int,
    val token: String,
    val signature: String,
)

@Serializable
data class HeartbeatMessage(
    val type: String = "heartbeat",
    @SerialName("battery_level") val batteryLevel: Int? = null,
    @SerialName("sim_state") val simState: String? = null,
    @SerialName("network_state") val networkState: String? = null,
    @SerialName("app_version") val appVersion: String? = null,
    @SerialName("phone_model") val phoneModel: String? = null,
    @SerialName("android_version") val androidVersion: String? = null,
)

@Serializable
data class MessageResultMessage(
    val type: String = "message_result",
    @SerialName("message_id") val messageId: String,
    val status: String, // SEND_SUCCESS | SEND_FAILED
    val error: String? = null,
    val timestamp: String? = null,
)

@Serializable
data class IncomingSmsMessage(
    val type: String = "incoming_sms",
    val sender: String,
    val body: String,
    @SerialName("received_at") val receivedAt: String? = null,
)

@Serializable
data class PongMessage(val type: String = "pong")
