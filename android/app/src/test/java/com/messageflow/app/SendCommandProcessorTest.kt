package com.messageflow.app

import com.messageflow.app.data.FakeSmsSender
import com.messageflow.app.data.ResultStore
import com.messageflow.app.data.SendCommandProcessor
import com.messageflow.app.data.protocol.SendMessageCommand
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class InMemoryResultStore : ResultStore {
    private val map = mutableMapOf<String, String>()
    override suspend fun saveResult(messageId: String, resultJson: String) {
        map[messageId] = resultJson
    }

    override suspend fun findResult(messageId: String): String? = map[messageId]

    override suspend fun clearResults() = map.clear()
}

class SendCommandProcessorTest {

    private fun command(messageId: String, phone: String = "+919876543210") =
        SendMessageCommand(
            commandId = "cmd-$messageId",
            messageId = messageId,
            idempotencyKey = "key-$messageId",
            phone = phone,
            message = "Hello from MessageFlow!",
        )

    @Test
    fun `sends message and reports success from device result`() = runTest {
        val store = InMemoryResultStore()
        val sender = FakeSmsSender()
        val processor = SendCommandProcessor(store, sender)

        val result = processor.handle(command("m1"))

        assertEquals("SEND_SUCCESS", result.status)
        assertFalse(result.replayed)
        assertEquals(1, sender.sent.size)
        assertEquals("m1", sender.sent[0].first)
        assertEquals("+919876543210", sender.sent[0].second)
        // Result stored for idempotency.
        assertTrue(store.findResult("m1") != null)
    }

    @Test
    fun `reports failure from device result with error`() = runTest {
        val store = InMemoryResultStore()
        val sender = FakeSmsSender(autoEmit = false)
        val processor = SendCommandProcessor(store, sender)

        val deferred = CompletableDeferred<SendCommandProcessor.ProcessedResult>()
        launch { deferred.complete(processor.handle(command("m2"))) }

        // The device reports a real failure for the SMS operation.
        sender.emit("m2", success = false, error = "RESULT_ERROR_NO_SERVICE")

        val result = deferred.await()
        assertEquals("SEND_FAILED", result.status)
        assertEquals("RESULT_ERROR_NO_SERVICE", result.error)
        assertEquals(1, sender.sent.size)
    }

    @Test
    fun `does not resend a command whose result is already stored`() = runTest {
        val store = InMemoryResultStore()
        val sender = FakeSmsSender()
        val processor = SendCommandProcessor(store, sender)

        processor.handle(command("m3"))
        assertEquals(1, sender.sent.size)

        // Same message_id again (reconnect / server retry): replayed, not re-sent.
        val replay = processor.handle(command("m3"))
        assertEquals(1, sender.sent.size)
        assertEquals("SEND_SUCCESS", replay.status)
        assertTrue(replay.replayed)
    }

    @Test
    fun `messages are paced by the local safety interval`() = kotlinx.coroutines.runBlocking {
        val store = InMemoryResultStore()
        val sender = FakeSmsSender()
        val processor = SendCommandProcessor(store, sender)

        val start = System.currentTimeMillis()
        processor.handle(command("m-a"))
        processor.handle(command("m-b"))
        val elapsed = System.currentTimeMillis() - start

        assertEquals(2, sender.sent.size)
        // Local pacing floor between SMS operations (3s) - real time here.
        assertTrue("expected pacing delay, took ${elapsed}ms", elapsed >= 2_500)
    }

    @Test
    fun `replays stored failure instead of resending`() = runTest {
        val store = InMemoryResultStore()
        val sender = FakeSmsSender(autoEmit = false)
        val processor = SendCommandProcessor(store, sender)

        val deferred = CompletableDeferred<SendCommandProcessor.ProcessedResult>()
        launch { deferred.complete(processor.handle(command("m4"))) }
        sender.emit("m4", success = false, error = "RESULT_ERROR_RADIO_OFF")
        assertEquals("SEND_FAILED", deferred.await().status)
        assertEquals(1, sender.sent.size)

        // Server retries the same message after reconnect.
        val retry = processor.handle(command("m4"))
        assertEquals("SEND_FAILED", retry.status)
        assertEquals("RESULT_ERROR_RADIO_OFF", retry.error)
        assertTrue(retry.replayed)
        assertEquals(1, sender.sent.size) // never sent twice
    }
}
