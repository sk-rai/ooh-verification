package com.trustcapture.vendor.data.remote.api

import com.trustcapture.vendor.data.remote.dto.PhotoUploadResponse
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part

interface PhotoApi {

    @Multipart
    @POST("api/photos/upload")
    suspend fun uploadPhoto(
        @Part photo: MultipartBody.Part,
        @Part("sensor_data") sensorData: RequestBody,
        @Part("signature") signature: RequestBody,
        @Part("campaign_code") campaignCode: RequestBody,
        @Part("capture_timestamp") captureTimestamp: RequestBody
    ): Response<PhotoUploadResponse>
}
