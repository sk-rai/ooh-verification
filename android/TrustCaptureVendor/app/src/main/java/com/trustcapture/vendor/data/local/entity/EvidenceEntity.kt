package com.trustcapture.vendor.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "evidence_queue")
data class EvidenceEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val evidenceType: String, // "photo", "video", "voice_note"
    val filePath: String, // Local file path (cached)
    val fileName: String,
    val mimeType: String,
    val campaignId: String?,
    val campaignCode: String?,
    val category: String?,
    val textContent: String?,
    val sensorDataJson: String?,
    val signatureJson: String?,
    val gpsTrackJson: String?,
    val captureTimestamp: String,
    val status: String = "pending", // pending, uploading, uploaded, failed
    val retryCount: Int = 0,
    val errorMessage: String? = null,
    val createdAt: Long = System.currentTimeMillis()
)
