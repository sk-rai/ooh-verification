package com.trustcapture.vendor.data.local.entity

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "audit_logs",
    indices = [
        Index(value = ["eventType"]),
        Index(value = ["vendorId"]),
        Index(value = ["timestamp"]),
        Index(value = ["synced"])
    ]
)
data class AuditEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val eventType: String, // PHOTO_CAPTURED, PHOTO_ENCRYPTED, PHOTO_UPLOADED, UPLOAD_FAILED, etc.
    val photoId: Long? = null,
    val vendorId: String,
    val deviceId: String, // Keystore key alias or device fingerprint
    val details: String? = null, // JSON with extra context
    val emulatorMode: Boolean = false, // true if event occurred on emulator (Req 19.1)
    val synced: Boolean = false,
    val timestamp: Long = System.currentTimeMillis()
)
