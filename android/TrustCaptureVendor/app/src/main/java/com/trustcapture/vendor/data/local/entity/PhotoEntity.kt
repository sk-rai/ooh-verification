package com.trustcapture.vendor.data.local.entity

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

enum class UploadStatus {
    PENDING, UPLOADING, UPLOADED, FAILED
}

@Entity(
    tableName = "photos",
    indices = [
        Index(value = ["uploadStatus"]),
        Index(value = ["campaignId"]),
        Index(value = ["vendorId"]),
        Index(value = ["capturedAt"]),
        Index(value = ["campaignId", "uploadStatus"])
    ]
)
data class PhotoEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val campaignId: String,
    val campaignCode: String,
    val campaignType: String = "",
    val vendorId: String,
    val originalUri: String,
    val encryptedPath: String,
    val sensorDataJson: String,
    val signatureJson: String,
    val latitude: Double?,
    val longitude: Double?,
    val confidenceScore: Int?,
    val triangulationFlags: String?, // comma-separated flags
    val safetyTags: String? = null, // comma-separated safety tags (construction)
    val roomLabel: String? = null, // room label (property management)
    val photoSequence: Int? = null, // sequential number (insurance)
    val hipaaCompliant: Boolean = false, // HIPAA flag (healthcare)
    val emulatorMode: Boolean = false, // true if captured on emulator (Req 19.1)
    val capturedAt: Long, // epoch millis
    val uploadStatus: String = UploadStatus.PENDING.name,
    val retryCount: Int = 0,
    val lastError: String? = null,
    val createdAt: Long = System.currentTimeMillis()
)
