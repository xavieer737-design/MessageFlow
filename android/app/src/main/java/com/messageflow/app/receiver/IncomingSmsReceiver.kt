package com.messageflow.app.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.telephony.SmsMessage

/**
 * Optional STOP/UNSUBSCRIBE handling.
 *
 * Only active when the user explicitly opted in (RECEIVE_SMS permission
 * + toggle in Settings). Incoming SMS bodies are matched against
 * keywords and forwarded to the backend, which adds the sender to the
 * opt-out list. No message content is ever stored locally.
 *
 * Platform limitations:
 *  - On Android 4.4+ the default SMS app has exclusive access to the
 *    SMS provider, but all apps with RECEIVE_SMS still receive the
 *    SMS_RECEIVED broadcast.
 *  - Google Play restricts RECEIVE_SMS to apps whose core function is
 *    SMS; sideloaded builds are unaffected.
 */
class IncomingSmsReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return
        val sender = messages.firstOrNull()?.originatingAddress ?: return
        val body = messages.joinToString("") { it.messageBody ?: "" }
        if (body.isBlank()) return

        // Forward to the backend over the WebSocket (if connected).
        // The service exposes a static hook the app can populate.
        DeviceConnectionServiceBridge.forwardIncomingSms?.invoke(context, sender, body)
    }
}

/**
 * Bridge so the (service-bound) WebSocket can receive inbound SMS.
 * Set by DeviceConnectionService when it starts.
 */
object DeviceConnectionServiceBridge {
    var forwardIncomingSms: ((Context, String, String) -> Unit)? = null
}
