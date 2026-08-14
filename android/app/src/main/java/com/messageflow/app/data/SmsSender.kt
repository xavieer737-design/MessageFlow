package com.messageflow.app.data

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.telephony.SmsManager
import android.util.Log
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.receiveAsFlow

/**
 * Wraps Android's official SmsManager API. Each send registers a
 * broadcast receiver that reports the REAL result code delivered by the
 * system after the SMS operation - never a guessed status.
 *
 * Result codes (android.telephony.SmsManager):
 *  - RESULT_ERROR_GENERIC_FAILURE, RESULT_ERROR_NO_SERVICE,
 *    RESULT_ERROR_NULL_PDU, RESULT_ERROR_RADIO_OFF, RESULT_ERROR_SHORT_CODE_NEVER_ALLOWED
 *  - RESULT_ERROR_SHORT_CODE_NOT_ALLOWED, RESULT_ERROR_LIMIT_EXCEEDED,
 *    RESULT_ERROR_FDN_CHECK_FAILED, RESULT_ERROR_UNSUPPORTED_URI
 *  - RESULT_ERROR_MESSAGE_SIZE_EXCEEDED
 */

data class SmsSendOutcome(
    val messageId: String,
    val success: Boolean,
    val error: String?,
)

interface SmsSender {
    /** Send one message (multi-part when needed). Result delivered via [results]. */
    fun send(messageId: String, phone: String, text: String)
    val results: kotlinx.coroutines.flow.Flow<SmsSendOutcome>
}

class AndroidSmsSender(private val context: Context) : SmsSender {

    private val channel = Channel<SmsSendOutcome>(Channel.UNLIMITED)
    override val results = channel.receiveAsFlow()

    override fun send(messageId: String, phone: String, text: String) {
        val smsManager = SmsManager.getDefault()
        val sentIntent = PendingIntent.getBroadcast(
            context,
            messageId.hashCode(),
            Intent(SENT_ACTION).setPackage(context.packageName).putExtra(EXTRA_MESSAGE_ID, messageId),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                val id = intent.getStringExtra(EXTRA_MESSAGE_ID) ?: messageId
                val resultCode = resultCode
                if (resultCode == android.app.Activity.RESULT_OK) {
                    channel.trySend(SmsSendOutcome(id, success = true, error = null))
                } else {
                    channel.trySend(SmsSendOutcome(id, success = false, error = resultCodeToError(resultCode)))
                }
                context.unregisterReceiver(this)
            }
        }
        context.registerReceiver(receiver, IntentFilter(SENT_ACTION))

        try {
            if (text.length > SMS_MAX_CHARS_GSM) {
                smsManager.sendMultipartTextMessage(
                    phone, null, smsManager.divideMessage(text),
                    listOf(sentIntent), null,
                )
            } else {
                smsManager.sendTextMessage(phone, null, text, sentIntent, null)
            }
        } catch (e: Exception) {
            Log.e(TAG, "SmsManager threw: ${e.message}", e)
            runCatching { context.unregisterReceiver(receiver) }
            channel.trySend(
                SmsSendOutcome(messageId, success = false, error = "exception: ${e.message}")
            )
        }
    }

    private fun resultCodeToError(code: Int): String = when (code) {
        SmsManager.RESULT_ERROR_GENERIC_FAILURE -> "RESULT_ERROR_GENERIC_FAILURE"
        SmsManager.RESULT_ERROR_NO_SERVICE -> "RESULT_ERROR_NO_SERVICE"
        SmsManager.RESULT_ERROR_NULL_PDU -> "RESULT_ERROR_NULL_PDU"
        SmsManager.RESULT_ERROR_RADIO_OFF -> "RESULT_ERROR_RADIO_OFF"
        SmsManager.RESULT_ERROR_SHORT_CODE_NEVER_ALLOWED -> "RESULT_ERROR_SHORT_CODE_NEVER_ALLOWED"
        SmsManager.RESULT_ERROR_SHORT_CODE_NOT_ALLOWED -> "RESULT_ERROR_SHORT_CODE_NOT_ALLOWED"
        SmsManager.RESULT_ERROR_LIMIT_EXCEEDED -> "RESULT_ERROR_LIMIT_EXCEEDED"
        SmsManager.RESULT_ERROR_FDN_CHECK_FAILED -> "RESULT_ERROR_FDN_CHECK_FAILED"
        SmsManager.RESULT_ERROR_UNSUPPORTED_URI -> "RESULT_ERROR_UNSUPPORTED_URI"
        SmsManager.RESULT_ERROR_MESSAGE_SIZE_EXCEEDED -> "RESULT_ERROR_MESSAGE_SIZE_EXCEEDED"
        else -> "UNKNOWN_RESULT_CODE($code)"
    }

    companion object {
        private const val TAG = "SmsSender"
        private const val SENT_ACTION = "com.messageflow.app.SMS_SENT"
        private const val EXTRA_MESSAGE_ID = "message_id"
        private const val SMS_MAX_CHARS_GSM = 160
    }
}

/** Test double used by unit tests. */
class FakeSmsSender(private val autoEmit: Boolean = true) : SmsSender {
    val sent = mutableListOf<Triple<String, String, String>>() // messageId, phone, text
    private val channel = Channel<SmsSendOutcome>(Channel.UNLIMITED)
    override val results = channel.receiveAsFlow()

    override fun send(messageId: String, phone: String, text: String) {
        sent.add(Triple(messageId, phone, text))
        if (autoEmit) {
            channel.trySend(SmsSendOutcome(messageId, true, null))
        }
    }

    fun emit(messageId: String, success: Boolean, error: String? = null) {
        channel.trySend(SmsSendOutcome(messageId, success, error))
    }
}
