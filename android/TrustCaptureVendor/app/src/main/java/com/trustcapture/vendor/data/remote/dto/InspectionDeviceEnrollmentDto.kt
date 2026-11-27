package com.trustcapture.vendor.data.remote.dto

import com.google.gson.annotations.SerializedName

data class InspectionDeviceEnrollmentDto(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("enrollment_proof") val enrollmentProof: String,
    @SerializedName("public_key") val publicKey: String,
    @SerializedName("proof_signature") val proofSignature: String
)

data class InspectionDeviceEnrollmentResultDto(
    @SerializedName("key_id") val keyId: String,
    @SerializedName("key_fingerprint") val keyFingerprint: String
)
