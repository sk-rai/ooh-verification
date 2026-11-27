package com.trustcapture.vendor.domain.repository

import com.trustcapture.vendor.data.local.db.InspectionEvidenceDao
import com.trustcapture.vendor.data.remote.api.InspectionVisitApi
import java.io.File
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

class InspectionEvidenceRepository(
    private val dao: InspectionEvidenceDao,
    private val stagingApi: InspectionVisitApi,
    private val mediaDirectory: File,
    private val trace: (String) -> Unit = {}
) {
    private val attemptLock = Mutex()

    suspend fun finalizePending(
        tenantId: String,
        vendorId: String,
        reservationId: String
    ): InspectionFinalizationOutcome = attemptLock.withLock {
        val row = dao.read(tenantId, vendorId, reservationId) ?: return@withLock InspectionFinalizationOutcome.HOLD
        if (row.evidenceId != null) {
            if (row.eligible == true) cleanup(row.mediaPath)
            return@withLock InspectionFinalizationOutcome.COMPLETE
        }
        if (row.held) return@withLock InspectionFinalizationOutcome.HOLD
        val pending = PendingInspectionFinalization(reservationId, row.visitId, tenantId, vendorId, row.requestJson)
        val outcome = finalizeInspectionEvidence(
            pending = pending,
            send = { request ->
                val response = stagingApi.finalizeCapture(
                    request.visitId, request.reservationId,
                    request.requestJson.toRequestBody("application/json".toMediaType())
                )
                response.code() to response.body()
            },
            commitAcknowledgement = { request, ack ->
                val committed = dao.acknowledge(
                    request.tenantId, request.vendorId, request.reservationId, request.requestJson,
                    ack.receiptId, ack.evidenceId, ack.eligible
                ) == 1
                if (committed) {
                    trace("Acknowledgement saved; reservation=$reservationId receipt=${ack.receiptId} evidence=${ack.evidenceId} eligible=${ack.eligible}")
                }
                committed
            },
            cleanupMedia = {
                if (dao.read(tenantId, vendorId, reservationId)?.eligible == true) {
                    cleanup(row.mediaPath)
                    trace("Media cleanup checked; reservation=$reservationId present=${File(row.mediaPath).exists()}")
                }
            }
        )
        if (outcome == InspectionFinalizationOutcome.HOLD) {
            dao.hold(tenantId, vendorId, reservationId, row.requestJson)
        }
        outcome
    }

    private suspend fun cleanup(mediaPath: String) = withContext(Dispatchers.IO) {
        try {
            val root = mediaDirectory.canonicalFile.toPath()
            val media = File(mediaPath).canonicalFile
            if (media.toPath() != root && media.toPath().startsWith(root)) media.delete()
        } catch (_: IOException) {
            // The acknowledgement is durable. A subsequent cleanup can try again.
        }
        Unit
    }
}
