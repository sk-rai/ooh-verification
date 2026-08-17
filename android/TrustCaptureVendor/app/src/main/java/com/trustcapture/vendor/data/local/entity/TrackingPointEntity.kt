package com.trustcapture.vendor.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "tracking_points")
data class TrackingPointEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val latitude: Double,
    val longitude: Double,
    val accuracy: Float,
    val timestampMs: Long,
    val batteryPct: Int?,
    val synced: Boolean = false
)
