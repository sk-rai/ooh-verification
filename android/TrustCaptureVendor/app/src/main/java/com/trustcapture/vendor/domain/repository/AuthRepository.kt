package com.trustcapture.vendor.domain.repository

import android.provider.Settings
import android.content.Context
import com.trustcapture.vendor.data.local.datastore.UserPreferences
import com.trustcapture.vendor.data.remote.api.AuthApi
import com.trustcapture.vendor.data.remote.dto.OtpRequest
import com.trustcapture.vendor.data.remote.dto.OtpResponse
import com.trustcapture.vendor.data.remote.dto.OtpVerifyRequest
import com.trustcapture.vendor.data.remote.dto.RegisterDeviceRequest
import com.trustcapture.vendor.util.KeystoreManager
import com.trustcapture.vendor.util.Resource
import com.trustcapture.vendor.util.safeApiCall
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val authApi: AuthApi,
    private val userPreferences: UserPreferences,
    private val keystoreManager: KeystoreManager,
    @ApplicationContext private val context: Context
) {
    val isLoggedIn: Flow<Boolean> = userPreferences.isLoggedIn

    private fun getDeviceId(): String {
        return Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
    }

    suspend fun requestOtp(phoneNumber: String, vendorId: String): Resource<OtpResponse> {
        return safeApiCall { authApi.requestOtp(OtpRequest(phoneNumber, vendorId)) }
    }

    suspend fun verifyOtp(phoneNumber: String, vendorId: String, otp: String): Resource<Unit> {
        val result = safeApiCall {
            authApi.verifyOtp(
                OtpVerifyRequest(
                    phoneNumber = phoneNumber,
                    vendorId = vendorId,
                    otp = otp,
                    deviceId = getDeviceId()
                )
            )
        }
        return when (result) {
            is Resource.Success -> {
                val data = result.data
                userPreferences.saveAuthData(data.accessToken, "")
                userPreferences.saveVendorInfo(vendorId, phoneNumber)

                // Generate Keystore key pair on first login and register device
                registerDeviceIfNeeded()

                Resource.Success(Unit)
            }
            is Resource.Error -> Resource.Error(result.message, result.code)
            is Resource.Loading -> Resource.Loading
        }
    }

    /**
     * Generates ECDSA key pair in Android Keystore (if not already present)
     * and registers the public key with the backend.
     */
    private suspend fun registerDeviceIfNeeded() {
        keystoreManager.generateKeyPairIfNeeded()

        val publicKeyPem = keystoreManager.getPublicKeyPem() ?: return
        val deviceId = getDeviceId()

        // Best-effort registration — don't fail login if this fails
        try {
            safeApiCall {
                authApi.registerDevice(
                    RegisterDeviceRequest(
                        deviceId = deviceId,
                        publicKey = publicKeyPem
                    )
                )
            }
        } catch (_: Exception) {
            // Will retry on next login
        }
    }

    suspend fun logout() {
        userPreferences.clear()
    }
}
