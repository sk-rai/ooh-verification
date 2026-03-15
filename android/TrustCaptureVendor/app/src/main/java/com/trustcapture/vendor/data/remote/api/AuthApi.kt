package com.trustcapture.vendor.data.remote.api

import com.trustcapture.vendor.data.remote.dto.AuthTokenResponse
import com.trustcapture.vendor.data.remote.dto.OtpRequest
import com.trustcapture.vendor.data.remote.dto.OtpResponse
import com.trustcapture.vendor.data.remote.dto.OtpVerifyRequest
import com.trustcapture.vendor.data.remote.dto.RegisterDeviceRequest
import com.trustcapture.vendor.data.remote.dto.VendorProfileResponse
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface AuthApi {

    @POST("api/auth/vendor/request-otp")
    suspend fun requestOtp(@Body request: OtpRequest): Response<OtpResponse>

    @POST("api/auth/vendor/verify-otp")
    suspend fun verifyOtp(@Body request: OtpVerifyRequest): Response<AuthTokenResponse>

    @POST("api/auth/vendor/register-device")
    suspend fun registerDevice(@Body request: RegisterDeviceRequest): Response<VendorProfileResponse>

    @GET("api/auth/me/vendor")
    suspend fun getVendorProfile(): Response<VendorProfileResponse>
}
