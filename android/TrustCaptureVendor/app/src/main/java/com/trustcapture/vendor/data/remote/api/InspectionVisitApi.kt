package com.trustcapture.vendor.data.remote.api

import com.trustcapture.vendor.data.remote.dto.InspectionPackageDto
import com.trustcapture.vendor.data.remote.dto.InspectionDeviceEnrollmentDto
import com.trustcapture.vendor.data.remote.dto.InspectionDeviceEnrollmentResultDto
import com.google.gson.JsonObject
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface InspectionVisitApi {
    @POST("api/auth/vendor/inspection-device")
    suspend fun enrollDevice(
        @Body request: InspectionDeviceEnrollmentDto
    ): Response<InspectionDeviceEnrollmentResultDto>

    @GET("api/inspection-visits/{visit_id}/package")
    suspend fun getPackage(
        @Path("visit_id") visitId: String,
        @Query("owner_client_id") ownerClientId: String,
        @Query("assignment_id") assignmentId: String,
        @Query("generation") generation: Long
    ): Response<InspectionPackageDto>

    @POST("api/inspection-visits/{visit_id}/capture-reservations")
    suspend fun reserveCapture(
        @Path("visit_id") visitId: String,
        @Body request: RequestBody
    ): Response<JsonObject>

    @PUT("api/inspection-visits/{visit_id}/capture-reservations/{reservation_id}/original")
    suspend fun uploadOriginal(
        @Path("visit_id") visitId: String,
        @Path("reservation_id") reservationId: String,
        @Query("owner_client_id") ownerClientId: String,
        @Query("assignment_id") assignmentId: String,
        @Query("generation") generation: Long,
        @Body original: RequestBody
    ): Response<JsonObject>

    @POST("api/inspection-visits/{visit_id}/capture-reservations/{reservation_id}/finalize")
    suspend fun finalizeCapture(
        @Path("visit_id") visitId: String,
        @Path("reservation_id") reservationId: String,
        @Body request: RequestBody
    ): Response<JsonObject>
}
