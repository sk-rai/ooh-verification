package com.trustcapture.vendor.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "pending_photos")
data class PendingPhotoEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val campaignId: String,
    val filePath: String,
    val latitude: Double,
    val longitude: Double,
    val capturedAt: String,
    val status: String = "pending" // pending, uploading, uploaded, failed
)
