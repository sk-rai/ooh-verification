package com.trustcapture.vendor

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.trustcapture.vendor.domain.repository.InspectionAcknowledgement
import com.trustcapture.vendor.domain.repository.InspectionFinalizationOutcome
import com.trustcapture.vendor.domain.repository.PendingInspectionFinalization
import com.trustcapture.vendor.domain.repository.finalizeInspectionEvidence
import java.io.IOException
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class InspectionFinalizationTest {
    @Test
    fun lostResponseReplaysOriginalEvidenceBeforeMediaCleanup() = runBlocking {
        val pending = PendingInspectionFinalization(
            "reservation", "visit", "tenant", "vendor",
            """{"owner_client_id":"owner","assignment_id":"assignment","generation":1,"document_instance_id":"document","field_id":"field","slot_id":"photo","repeat_item_id":"item-two","client_capture_id":"capture","upload_key":"upload","digest":"digest","byte_length":42}"""
        )
        val sent = mutableListOf<String>()
        val serverEvidence = mutableMapOf<String, JsonObject>()
        var acknowledgement: InspectionAcknowledgement? = null
        var mediaPresent = true
        val send: suspend (PendingInspectionFinalization) -> Pair<Int, JsonObject?> = { attempt ->
            sent.add(attempt.requestJson)
            val response = serverEvidence.getOrPut(attempt.requestJson) {
                JsonParser.parseString(attempt.requestJson).asJsonObject.apply {
                    addProperty("code", "CAPTURE_ACCEPTED")
                    addProperty("reservation_id", attempt.reservationId)
                    addProperty("visit_id", attempt.visitId)
                    addProperty("tenant_id", attempt.tenantId)
                    addProperty("vendor_id", attempt.vendorId)
                    addProperty("receipt_id", "original-receipt")
                    addProperty("evidence_id", "original-evidence")
                    addProperty("eligible", true)
                }
            }
            if (sent.size == 1) throw IOException("Response lost after commit")
            200 to response
        }
        val commit: suspend (PendingInspectionFinalization, InspectionAcknowledgement) -> Boolean = { request, ack ->
            assertEquals(pending, request)
            assertTrue(mediaPresent)
            acknowledgement = ack
            true
        }
        val cleanup: suspend (PendingInspectionFinalization) -> Unit = {
            assertEquals("original-evidence", acknowledgement?.evidenceId)
            mediaPresent = false
        }

        assertEquals(InspectionFinalizationOutcome.RETRY, finalizeInspectionEvidence(pending, send, commit, cleanup))
        assertNull(acknowledgement)
        assertTrue(mediaPresent)
        assertEquals(InspectionFinalizationOutcome.COMPLETE, finalizeInspectionEvidence(pending.copy(), send, commit, cleanup))
        assertEquals(listOf(pending.requestJson, pending.requestJson), sent)
        assertEquals(1, serverEvidence.size)
        assertEquals("item-two", serverEvidence.values.single()["repeat_item_id"].asString)
        assertEquals("original-receipt", acknowledgement?.receiptId)
        assertFalse(mediaPresent)
    }
}
