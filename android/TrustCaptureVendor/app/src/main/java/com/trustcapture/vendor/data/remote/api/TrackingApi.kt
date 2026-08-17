package com.trustcapture.vendor.data.remote.api

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST

interface TrackingApi {

    @POST("api/tracks/sync")
    suspend fun syncPoints(@Body body: TrackingSyncRequest): Response<TrackingSyncResponse>
}

data class TrackingSyncRequest(
    val points: List<TrackingPointPayload>
)

data class TrackingPointPayload(
    val lat: Double,
    val lon: Double,
    val accuracy: Float,
    @SerializedName("timestamp_ms") val timestampMs: Long,
    @SerializedName("battery_pct") val batteryPct: Int?
)

data class TrackingSyncResponse(
    val status: String,
    @SerializedName("track_id") val trackId: String?,
    @SerializedName("points_received") val pointsReceived: Int?,
    @SerializedName("total_points_today") val totalPointsToday: Int?,
    @SerializedName("distance_km") val distanceKm: Double?
)
