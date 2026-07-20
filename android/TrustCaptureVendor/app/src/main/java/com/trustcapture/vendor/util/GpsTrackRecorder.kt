package com.trustcapture.vendor.util

import com.google.gson.Gson
import com.google.gson.annotations.SerializedName

/**
 * Records GPS points during video capture at 1-second intervals.
 * Produces a JSON track array for upload.
 */
class GpsTrackRecorder {
    private val points = mutableListOf<GpsTrackPoint>()
    private var startTimeMs: Long = 0L

    val pointCount: Int get() = points.size
    val durationSeconds: Float get() = if (startTimeMs > 0)
        (System.currentTimeMillis() - startTimeMs) / 1000f else 0f

    fun start() {
        points.clear()
        startTimeMs = System.currentTimeMillis()
    }

    fun addPoint(latitude: Double, longitude: Double, accuracy: Float) {
        points.add(
            GpsTrackPoint(
                lat = latitude,
                lon = longitude,
                accuracy = accuracy,
                timestampMs = System.currentTimeMillis()
            )
        )
    }

    fun stop(): String {
        return Gson().toJson(points)
    }

    fun reset() {
        points.clear()
        startTimeMs = 0L
    }
}

data class GpsTrackPoint(
    @SerializedName("lat") val lat: Double,
    @SerializedName("lon") val lon: Double,
    @SerializedName("accuracy") val accuracy: Float,
    @SerializedName("timestamp_ms") val timestampMs: Long
)
