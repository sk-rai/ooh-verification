package com.trustcapture.vendor.domain.repository

import com.google.gson.JsonObject
import java.io.IOException

data class PendingInspectionFinalization(
    val reservationId: String,
    val visitId: String,
    val tenantId: String,
    val vendorId: String,
    val requestJson: String
)

data class InspectionAcknowledgement(
    val receiptId: String,
    val evidenceId: String,
    val eligible: Boolean
)

enum class InspectionFinalizationOutcome { COMPLETE, RETRY, HOLD }

/**
 * Runs one finalization attempt using the already durable request.
 * The acknowledgement writer must commit the receipt and exact binding together.
 */
suspend fun finalizeInspectionEvidence(
    pending: PendingInspectionFinalization,
    send: suspend (PendingInspectionFinalization) -> Pair<Int, JsonObject?>,
    commitAcknowledgement: suspend (PendingInspectionFinalization, InspectionAcknowledgement) -> Boolean,
    cleanupMedia: suspend (PendingInspectionFinalization) -> Unit
): InspectionFinalizationOutcome {
    val (status, body) = try {
        send(pending)
    } catch (_: IOException) {
        return InspectionFinalizationOutcome.RETRY
    }
    if (status == 408 || status == 429 || status in 500..599) return InspectionFinalizationOutcome.RETRY
    if (status !in setOf(200, 201) || body == null) return InspectionFinalizationOutcome.HOLD
    val request = com.google.gson.JsonParser.parseString(pending.requestJson).asJsonObject
    val targetFields = listOf(
        "owner_client_id", "assignment_id", "generation", "document_instance_id", "field_id",
        "slot_id", "repeat_item_id", "client_capture_id", "upload_key", "digest", "byte_length"
    )
    if (body.nonEmptyString("code") != "CAPTURE_ACCEPTED" ||
        body.nonEmptyString("reservation_id") != pending.reservationId ||
        body.nonEmptyString("visit_id") != pending.visitId ||
        body.nonEmptyString("tenant_id") != pending.tenantId ||
        body.nonEmptyString("vendor_id") != pending.vendorId ||
        targetFields.any { !body.has(it) || body[it] != (request[it] ?: com.google.gson.JsonNull.INSTANCE) }
    ) return InspectionFinalizationOutcome.HOLD

    val receiptId = body.nonEmptyString("receipt_id") ?: return InspectionFinalizationOutcome.HOLD
    val evidenceId = body.nonEmptyString("evidence_id") ?: return InspectionFinalizationOutcome.HOLD
    val eligible = body["eligible"]?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isBoolean }
        ?.asBoolean ?: return InspectionFinalizationOutcome.HOLD
    if (!commitAcknowledgement(pending, InspectionAcknowledgement(receiptId, evidenceId, eligible))) {
        return InspectionFinalizationOutcome.HOLD
    }
    cleanupMedia(pending)
    return InspectionFinalizationOutcome.COMPLETE
}

private fun JsonObject.nonEmptyString(name: String): String? =
    get(name)?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isString }?.asString?.takeIf { it.isNotBlank() }
