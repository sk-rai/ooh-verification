package com.trustcapture.vendor

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.trustcapture.vendor.data.local.db.InspectionEvidenceDao
import com.trustcapture.vendor.data.local.db.InspectionEvidenceFinalizationRow
import com.trustcapture.vendor.data.local.db.InspectionPendingCapture
import com.trustcapture.vendor.data.remote.api.InspectionVisitApi
import com.trustcapture.vendor.data.remote.dto.InspectionDeviceEnrollmentDto
import com.trustcapture.vendor.domain.repository.InspectionCaptureSync
import com.trustcapture.vendor.domain.repository.InspectionFinalizationOutcome
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import kotlinx.coroutines.runBlocking
import okhttp3.RequestBody
import okio.Buffer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import retrofit2.Response

class InspectionCaptureSyncTest {
    @get:Rule val files = TemporaryFolder()

    @Test
    fun afterLostFinalizationResponseResumesWithoutUploadingAgain() = runBlocking {
        val media = File(files.root, "synthetic.jpg").apply { writeText("synthetic original") }
        val digest = MessageDigest.getInstance("SHA-256").digest(media.readBytes())
            .joinToString("") { "%02x".format(it) }
        val request = """
            {"owner_client_id":"owner","assignment_id":"assignment","generation":1,"document_instance_id":"document",
            "field_id":"field","slot_id":"photo","repeat_item_id":"item-two","client_capture_id":"capture",
            "upload_key":"upload","digest":"$digest","byte_length":${media.length()}}
        """.trimIndent()
        val store = FakeStore(InspectionPendingCapture("capture", "tenant", "vendor", "visit", media.path, request, "key", "signature"))
        val server = FakeServer()

        suspend fun nextAttempt() = InspectionCaptureSync(store, server, files.root)
            .sync("tenant", "vendor", "visit", "owner", "assignment", 1).single()

        assertEquals(InspectionFinalizationOutcome.RETRY, nextAttempt())
        assertTrue(media.exists())
        assertEquals(null, store.finalization?.evidenceId)
        assertEquals(InspectionFinalizationOutcome.COMPLETE, nextAttempt())
        assertEquals(1, server.reserves)
        assertEquals(1, server.uploads)
        assertEquals(2, server.finalizations.size)
        assertEquals(server.finalizations[0], server.finalizations[1])
        assertEquals(1, server.committed.size)
        assertEquals("original-evidence", store.finalization?.evidenceId)
        assertEquals("item-two", JsonParser.parseString(store.finalization?.requestJson).asJsonObject["repeat_item_id"].asString)
        assertFalse(media.exists())
    }

    private class FakeStore(var capture: InspectionPendingCapture) : InspectionEvidenceDao {
        var finalization: InspectionEvidenceFinalizationRow? = null
        override suspend fun insertPendingCapture(row: InspectionPendingCapture) = error("Already queued")
        override suspend fun readCaptures(tenantId: String, vendorId: String, visitId: String) = listOf(capture)
        override suspend fun recordReservation(captureId: String, reservationId: String): Int {
            capture = capture.copy(reservationId = reservationId)
            return 1
        }
        override suspend fun recordOriginal(captureId: String, reservationId: String): Int {
            capture = capture.copy(originalStored = true)
            return 1
        }
        override suspend fun holdCapture(captureId: String) { capture = capture.copy(held = true) }
        override suspend fun insert(row: InspectionEvidenceFinalizationRow) {
            if (finalization == null) finalization = row
        }
        override suspend fun read(tenantId: String, vendorId: String, reservationId: String) = finalization
        override suspend fun acknowledge(
            tenantId: String, vendorId: String, reservationId: String, requestJson: String,
            receiptId: String, evidenceId: String, eligible: Boolean
        ): Int {
            assertTrue(File(capture.mediaPath).exists())
            finalization = requireNotNull(finalization).copy(receiptId = receiptId, evidenceId = evidenceId, eligible = eligible)
            return 1
        }
        override suspend fun hold(tenantId: String, vendorId: String, reservationId: String, requestJson: String) =
            error("Unexpected hold")
    }

    private class FakeServer : InspectionVisitApi {
        var reserves = 0
        var uploads = 0
        val finalizations = mutableListOf<String>()
        val committed = mutableMapOf<String, JsonObject>()
        override suspend fun enrollDevice(request: InspectionDeviceEnrollmentDto) = error("Already enrolled")
        override suspend fun getPackage(visitId: String, ownerClientId: String, assignmentId: String, generation: Long) =
            error("Already pinned")

        override suspend fun reserveCapture(visitId: String, request: RequestBody): Response<JsonObject> {
            reserves++
            return Response.success(201, responseBody(request.text(), "CAPTURE_RESERVED"))
        }

        override suspend fun uploadOriginal(
            visitId: String, reservationId: String, ownerClientId: String, assignmentId: String,
            generation: Long, original: RequestBody
        ): Response<JsonObject> {
            uploads++
            assertEquals("synthetic original", original.text())
            return Response.success(JsonObject().apply {
                addProperty("code", "CAPTURE_ORIGINAL_STORED")
                addProperty("reservation_id", "reservation")
            })
        }

        override suspend fun finalizeCapture(
            visitId: String, reservationId: String, request: RequestBody
        ): Response<JsonObject> {
            val body = request.text()
            finalizations.add(body)
            val response = committed.getOrPut(body) {
                responseBody(body, "CAPTURE_ACCEPTED").apply {
                    addProperty("receipt_id", "receipt")
                    addProperty("evidence_id", "original-evidence")
                    addProperty("eligible", true)
                }
            }
            if (finalizations.size == 1) throw IOException("Response lost after commit")
            return Response.success(response)
        }

        private fun responseBody(json: String, code: String) = JsonParser.parseString(json).asJsonObject.apply {
            addProperty("code", code)
            addProperty("reservation_id", "reservation")
            addProperty("visit_id", "visit")
            addProperty("tenant_id", "tenant")
            addProperty("vendor_id", "vendor")
        }

        private fun RequestBody.text(): String = Buffer().also { writeTo(it) }.readUtf8()
    }
}
