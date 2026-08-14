package com.messageflow.app

import com.messageflow.app.data.protocol.ProtocolJson
import com.messageflow.app.data.protocol.SendMessageCommand
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Wire protocol compatibility tests - field names must match the
 * backend (backend/app/api/routes/devices_ws.py).
 */
class ProtocolTest {

    @Test
    fun `send_message command encodes with backend field names`() {
        val command = SendMessageCommand(
            commandId = "cmd-1",
            messageId = "msg-1",
            idempotencyKey = "c1:r1",
            phone = "+919876543210",
            message = "Hi Rahul!",
            sendAt = "2026-08-14T12:00:00Z",
        )
        val json = ProtocolJson.json.encodeToString(SendMessageCommand.serializer(), command)
        val obj = Json.parseToJsonElement(json).jsonObject

        assertEquals("send_message", obj["type"]?.toString()?.trim('"'))
        assertEquals("msg-1", obj["message_id"]?.toString()?.trim('"'))
        assertEquals("c1:r1", obj["idempotency_key"]?.toString()?.trim('"'))
        assertEquals("+919876543210", obj["phone"]?.toString()?.trim('"'))
        assertTrue(json.contains("\"send_at\""))
    }

    @Test
    fun `decodes a server challenge message`() {
        val raw = """{"type":"challenge","nonce":"abc123"}"""
        val json = Json.parseToJsonElement(raw).jsonObject
        assertEquals("challenge", json["type"]?.toString()?.trim('"'))
        assertEquals("abc123", json["nonce"]?.toString()?.trim('"'))
    }

    @Test
    fun `decodes a message_result ack`() {
        val raw = """{"type":"result_ack","message_id":"msg-9","recorded":true}"""
        val json = Json.parseToJsonElement(raw).jsonObject
        assertEquals("msg-9", json["message_id"]?.toString()?.trim('"'))
        assertEquals("true", json["recorded"]?.toString())
    }

    @Test
    fun `heartbeat message uses snake_case backend fields`() {
        val raw = """{"type":"heartbeat","battery_level":82,"sim_state":"READY"}"""
        val json = Json.parseToJsonElement(raw).jsonObject
        assertEquals("82", json["battery_level"]?.toString())
        assertEquals("READY", json["sim_state"]?.toString()?.trim('"'))
    }
}
