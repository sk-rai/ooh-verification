package com.trustcapture.vendor.domain.repository

import com.google.gson.JsonNull
import com.google.gson.JsonObject
import com.google.gson.JsonParseException
import com.google.gson.JsonParser
import com.trustcapture.vendor.data.local.db.InspectionEvidenceDao
import com.trustcapture.vendor.data.local.db.InspectionEvidenceFinalizationRow
import com.trustcapture.vendor.data.local.db.InspectionPendingCapture
import com.trustcapture.vendor.data.remote.api.InspectionVisitApi
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Response

class InspectionCaptureSync(
    private val dao: InspectionEvidenceDao,
    private val api: InspectionVisitApi,
    private val mediaDirectory: File,
    trace: (String) -> Unit = {}
) {
    private val lock = Mutex()
    private val finalizer = InspectionEvidenceRepository(dao, api, mediaDirectory, trace)

    suspend fun sync(
        tenantId: String, vendorId: String, visitId: String,
        ownerClientId: String, assignmentId: String, generation: Long
    ): List<InspectionFinalizationOutcome> = lock.withLock {
        dao.readCaptures(tenantId, vendorId, visitId).map { capture ->
            val outcome = if (capture.held) InspectionFinalizationOutcome.HOLD else try {
                val request = JsonParser.parseString(capture.reservationJson).asJsonObject
                if (request.string("owner_client_id") != ownerClientId ||
                    request.string("assignment_id") != assignmentId ||
                    request["generation"]?.asLong != generation
                ) InspectionFinalizationOutcome.HOLD else syncCapture(capture, request, ownerClientId, assignmentId, generation)
            } catch (_: JsonParseException) {
                InspectionFinalizationOutcome.HOLD
            } catch (_: IOException) {
                InspectionFinalizationOutcome.RETRY
            }
            if (outcome == InspectionFinalizationOutcome.HOLD && !capture.held) dao.holdCapture(capture.captureId)
            outcome
        }
    }

    private suspend fun syncCapture(
        capture: InspectionPendingCapture, request: JsonObject,
        ownerClientId: String, assignmentId: String, generation: Long
    ): InspectionFinalizationOutcome {
        val reservationId = capture.reservationId ?: run {
            val response = api.reserveCapture(capture.visitId, capture.reservationJson.toRequestBody(JSON))
            if (!response.isSuccessful) return response.failureOutcome()
            val body = response.body() ?: return InspectionFinalizationOutcome.HOLD
            val id = body.string("reservation_id")
            if (id.isNullOrBlank() || body.string("code") != "CAPTURE_RESERVED" ||
                body.string("visit_id") != capture.visitId || body.string("tenant_id") != capture.tenantId ||
                body.string("vendor_id") != capture.vendorId || request.entrySet().any { (name, value) ->
                    !body.has(name) || body[name] != (value ?: JsonNull.INSTANCE)
                }
            ) return InspectionFinalizationOutcome.HOLD
            if (dao.recordReservation(capture.captureId, id) != 1) return InspectionFinalizationOutcome.RETRY
            id
        }

        if (!capture.originalStored) {
            val bytes = readVerifiedOriginal(capture, request) ?: return InspectionFinalizationOutcome.HOLD
            val response = api.uploadOriginal(
                capture.visitId, reservationId, ownerClientId, assignmentId, generation, bytes.toRequestBody(JPEG)
            )
            if (!response.isSuccessful) return response.failureOutcome()
            val body = response.body() ?: return InspectionFinalizationOutcome.HOLD
            if (body.string("code") != "CAPTURE_ORIGINAL_STORED" || body.string("reservation_id") != reservationId) {
                return InspectionFinalizationOutcome.HOLD
            }
            if (dao.recordOriginal(capture.captureId, reservationId) != 1) return InspectionFinalizationOutcome.RETRY
        }

        val finalizeJson = request.deepCopy().apply {
            addProperty("key_id", capture.keyId)
            addProperty("signature", capture.signature)
        }.toString()
        dao.insert(
            InspectionEvidenceFinalizationRow(
                capture.tenantId, capture.vendorId, reservationId, capture.visitId, finalizeJson, capture.mediaPath
            )
        )
        val stored = dao.read(capture.tenantId, capture.vendorId, reservationId)
        if (stored?.requestJson != finalizeJson || stored.mediaPath != capture.mediaPath || stored.visitId != capture.visitId) {
            return InspectionFinalizationOutcome.HOLD
        }
        val outcome = finalizer.finalizePending(capture.tenantId, capture.vendorId, reservationId)
        if (outcome == InspectionFinalizationOutcome.COMPLETE &&
            dao.read(capture.tenantId, capture.vendorId, reservationId)?.eligible != true
        ) return InspectionFinalizationOutcome.HOLD
        return outcome
    }

    private suspend fun readVerifiedOriginal(capture: InspectionPendingCapture, request: JsonObject): ByteArray? =
        withContext(Dispatchers.IO) {
            val file = File(capture.mediaPath).canonicalFile
            val root = mediaDirectory.canonicalFile.toPath()
            val length = request["byte_length"]?.asLong ?: return@withContext null
            if (!file.toPath().startsWith(root) || !file.isFile || length !in 1L..10_485_760L ||
                file.length() != length
            ) return@withContext null
            val bytes = file.readBytes()
            val digest = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            bytes.takeIf { it.size.toLong() == length && digest == request.string("digest") }
        }

    private fun Response<*>.failureOutcome(): InspectionFinalizationOutcome =
        if (code() == 408 || code() == 429 || code() in 500..599) InspectionFinalizationOutcome.RETRY
        else InspectionFinalizationOutcome.HOLD

    private fun JsonObject.string(name: String): String? =
        get(name)?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isString }?.asString

    private companion object {
        val JSON = "application/json".toMediaType()
        val JPEG = "image/jpeg".toMediaType()
    }
}
