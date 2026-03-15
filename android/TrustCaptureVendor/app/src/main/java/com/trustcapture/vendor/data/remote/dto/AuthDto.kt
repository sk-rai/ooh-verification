package com.trustcapture.vendor.data.remote.dto

import com.google.gson.annotations.SerializedName

data class OtpRequest(
    @SerializedName("phone_number") val phoneNumber: String,
    @SerializedName("vendor_id") val vendorId: String
)

data class OtpResponse(
    @SerializedName("message") val message: String,
    @SerializedName("expires_in") val expiresIn: Int
)

data class OtpVerifyRequest(
    @SerializedName("phone_number") val phoneNumber: String,
    @SerializedName("vendor_id") val vendorId: String,
    @SerializedName("otp") val otp: String,
    @SerializedName("device_id") val deviceId: String? = null
)

data class AuthTokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("token_type") val tokenType: String,
    @SerializedName("expires_in") val expiresIn: Int
)

data class RegisterDeviceRequest(
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("public_key") val publicKey: String
)

data class VendorProfileResponse(
    @SerializedName("vendor_id") val vendorId: String,
    @SerializedName("name") val name: String,
    @SerializedName("phone_number") val phoneNumber: String,
    @SerializedName("email") val email: String?,
    @SerializedName("status") val status: String,
    @SerializedName("device_id") val deviceId: String?,
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("last_login_at") val lastLoginAt: String?
)
