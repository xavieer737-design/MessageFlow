package com.messageflow.app

import com.messageflow.app.data.QrPayloadParser
import org.junit.Assert.assertEquals
import org.junit.Test

class PairingPayloadTest {

    @Test
    fun `parses a valid QR payload`() {
        val payload = QrPayloadParser.parse(
            """{"mf":1,"server":"https://msg.example.com","token":"abc-123-xyz"}"""
        )
        assertEquals("https://msg.example.com", payload["server"])
        assertEquals("abc-123-xyz", payload["token"])
    }

    @Test
    fun `missing fields parse to empty strings`() {
        val payload = QrPayloadParser.parse("""{"mf":1}""")
        assertEquals("", payload["server"])
        assertEquals("", payload["token"])
    }
}
