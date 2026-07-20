package com.trustcapture.vendor.data.remote.api

import com.trustcapture.vendor.data.remote.dto.EvidenceUploadResponse
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part

/**
 * Evidence upload API — replaces /api/photos/upload for new captures.
 * Supports photo, video, voice notes, and text notes.
 * Old /api/photos/upload endpoint still works for backward compatibility.
 */
interface EvidenceApi {

    @Multipart
    @POST("api/evidence/upload")
    suspend fun uploadEvidence(
        @Part file: MultipartBody.Part?,  // Nullable for text-only notes
        @Part("evidence_type") evidenceType: RequestBody,
        @Part("campaign_id") campaignId: RequestBody?,
        @Part("campaign_code") campaignCode: RequestBody?,
        @Part("category") category: RequestBody?,
        @Part("text_content") textContent: RequestBody?,
        @Part("sensor_data") sensorData: RequestBody?,
        @Part("signature") signature: RequestBody?,
        @Part("gps_track") gpsTrack: RequestBody?,
        @Part("capture_timestamp") captureTimestamp: RequestBody?,
        @Part("notes") notes: RequestBody?
    ): Response<EvidenceUploadResponse>
}
