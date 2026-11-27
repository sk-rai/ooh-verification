package com.trustcapture.vendor.data.remote.dto

import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName

data class InspectionPackageDto(
    @SerializedName("visit_id") val visitId: String,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("owner_client_id") val ownerClientId: String,
    @SerializedName("vendor_id") val vendorId: String,
    @SerializedName("assignment_id") val assignmentId: String,
    @SerializedName("generation") val generation: Long,
    @SerializedName("expires_at") val expiresAt: String,
    @SerializedName("server_time") val serverTime: String,
    @SerializedName("revision") val revision: Long,
    @SerializedName("code") val code: String,
    @SerializedName("workflow_version_id") val workflowVersionId: String,
    @SerializedName("document_requirements") val documentRequirements: List<InspectionDocumentRequirementDto>,
    @SerializedName("documents") val documents: List<InspectionPackageDocumentDto>
)

data class InspectionDocumentRequirementDto(
    @SerializedName("id") val id: String,
    @SerializedName("position") val position: Int,
    @SerializedName("form_version_id") val formVersionId: String,
    @SerializedName("min_instances") val minInstances: Int,
    @SerializedName("max_instances") val maxInstances: Int,
    // Gson's JsonObject adapter rejects an explicit JSON null.
    @SerializedName("activation_condition") val activationCondition: JsonElement?
)

data class InspectionPackageDocumentDto(
    @SerializedName("id") val id: String,
    @SerializedName("form_version_id") val formVersionId: String,
    @SerializedName("ordinal") val ordinal: Int,
    @SerializedName("requirement_id") val requirementId: String,
    @SerializedName("instance_number") val instanceNumber: Int,
    @SerializedName("definition") val definition: JsonObject,
    @SerializedName("capture_targets") val captureTargets: List<InspectionCaptureTargetDto>
)

data class InspectionCaptureTargetDto(
    @SerializedName("field_id") val fieldId: String,
    @SerializedName("slot_id") val slotId: String,
    @SerializedName("repeat_item_id") val repeatItemId: String?,
    @SerializedName("required") val required: Boolean
)
