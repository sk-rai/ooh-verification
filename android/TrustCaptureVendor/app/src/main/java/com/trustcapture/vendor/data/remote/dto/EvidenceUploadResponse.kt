package com.trustcapture.vendor.data.remote.dto

import com.google.gson.annotations.SerializedName

/**
 * Response from POST /api/evidence/upload
 */
data class EvidenceUploadResponse(
    @SerializedName("evidence_id") val evidenceId: String,
    @SerializedName("evidence_type") val evidenceType: String,
    @SerializedName("verification_status") val verificationStatus: String,
    @SerializedName("verification_confidence") val verificationConfidence: Double?,
    @SerializedName("verification_flags") val verificationFlags: List<String>?,
    @SerializedName("file_url") val fileUrl: String?,
    @SerializedName("thumbnail_url") val thumbnailUrl: String?,
    @SerializedName("message") val message: String?
)
