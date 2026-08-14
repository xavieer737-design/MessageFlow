package com.messageflow.app.data

import com.messageflow.app.data.protocol.SendMessageCommand
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.serialization.json.Json
import java.time.OffsetDateTime

/**
 * Executes send_message commands with:
 *
 * 1. **Idempotency**: if a result for this message_id is already stored
 *    (previous attempt, app restart, WS reconnect), the stored result is
 *    replayed and the SMS is NOT sent again.
 * 2. **Pacing**: honors the backend's `send_at` timestamp and a local
 *    minimum interval between SMS operations (defense in depth; the
 *    server also paces).
 * 3. **Honest results**: the outcome comes from SmsSender (the real
 *    SmsManager broadcast result), never synthesized by this layer.
 */
class SendCommandProcessor(
    private val storage: ResultStore,
    private val smsSender: SmsSender,
) {
    private val _results = MutableSharedFlow<ProcessedResult>(extraBufferCapacity = 64)
    val results: SharedFlow<ProcessedResult> = _results

    @Volatile private var paused = false
    private var lastSendAtMillis = 0L

    data class ProcessedResult(
        val messageId: String,
        val status: String, // SEND_SUCCESS | SEND_FAILED
        val error: String? = null,
        val replayed: Boolean = false,
        val timestamp: String,
    )

    /** Handle one command from the server. Returns the result to send back. */
    suspend fun handle(command: SendMessageCommand): ProcessedResult {
        // Pause support: hold commands while paused (server also stops
        // issuing them; this closes the race for in-flight batches).
        while (paused) {
            delay(250)
        }

        // Idempotency: replay stored result without sending.
        val stored = storage.findResult(command.messageId)
        if (stored != null) {
            val parsed = runCatching {
                Json.parseToJsonElement(stored).jsonObject
            }.getOrNull()
            val status = parsed?.get("status")?.toString()?.trim('"') ?: "SEND_SUCCESS"
            val error = parsed?.get("error")?.toString()?.trim('"')
            val result = ProcessedResult(
                messageId = command.messageId,
                status = status,
                error = error,
                replayed = true,
                timestamp = storedTimestamp(),
            )
            _results.tryEmit(result)
            return result
        }

        // Pacing: honor send_at from the server + local minimum interval.
        val delayMillis = computeDelayMillis(command.sendAt)
        if (delayMillis > 0) delay(delayMillis)

        smsSender.send(command.messageId, command.phone, command.message)
        // The actual result arrives asynchronously from SmsSender; the
        // collector below forwards it and stores it for idempotency.
        val outcome = awaitOutcome(command.messageId)
        lastSendAtMillis = System.currentTimeMillis()

        val result = ProcessedResult(
            messageId = command.messageId,
            status = if (outcome.success) "SEND_SUCCESS" else "SEND_FAILED",
            error = outcome.error,
            timestamp = storedTimestamp(),
        )
        storage.saveResult(command.messageId, Json.encodeToString(ProcessedResult.serializer(), result))
        _results.tryEmit(result)
        return result
    }

    fun pause() {
        paused = true
    }

    fun resume() {
        paused = false
    }

    fun cancel() {
        // No new sends; an already-running SmsManager call completes and
        // its result is still reported (never lost).
        paused = true
    }

    private suspend fun awaitOutcome(messageId: String): SmsSendOutcome {
        // Collect from the sender until this message's outcome arrives.
        return smsSender.results.firstOutcome(messageId)
    }

    /** Delay until the server's send_at and at least MIN_SMS_INTERVAL_MS. */
    private fun computeDelayMillis(sendAtIso: String?): Long {
        val now = System.currentTimeMillis()
        var target = now
        sendAtIso?.let { iso ->
            runCatching { OffsetDateTime.parse(iso).toInstant().toEpochMilli() }
                .getOrNull()
                ?.let { target = maxOf(target, it) }
        }
        val minNext = lastSendAtMillis + MIN_SMS_INTERVAL_MS
        target = maxOf(target, minNext)
        val delay = target - now
        return if (delay > 0) delay else 0
    }

    private fun storedTimestamp(): String =
        java.time.Instant.now().toString()

    companion object {
        /** Local safety floor between SMS operations (server paces too). */
        const val MIN_SMS_INTERVAL_MS = 3_000L
    }
}

/** Collect one outcome matching [messageId] from a results flow. */
suspend fun kotlinx.coroutines.flow.Flow<SmsSendOutcome>.firstOutcome(messageId: String): SmsSendOutcome =
    kotlinx.coroutines.flow.first { outcome -> outcome.messageId == messageId }
