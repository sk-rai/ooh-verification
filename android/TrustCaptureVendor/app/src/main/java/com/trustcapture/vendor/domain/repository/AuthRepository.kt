package com.trustcapture.vendor.domain.repository

import android.content.Context
import android.provider.Settings
import android.util.Log
import com.trustcapture.vendor.data.local.datastore.UserPreferences
import com.trustcapture.vendor.data.remote.api.AuthApi
import com.trustcapture.vendor.data.remote.dto.ChallengeRequest
import com.trustcapture.vendor.data.remote.dto.DeviceLoginRequest
import com.trustcapture.vendor.data.remote.dto.OtpRequest
import com.trustcapture.vendor.data.remote.dto.OtpResponse
import com.trustcapture.vendor.data.remote.dto.OtpVerifyRequest
import com.trustcapture.vendor.data.remote.dto.RegisterDeviceRequest
import com.trustcapture.vendor.util.KeystoreManager
import com.trustcapture.vendor.util.Resource
import com.trustcapture.vendor.util.safeApiCall
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

private const val TAG = "AuthRepository"

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

    /** Check if this device has been registered with the backend (public key stored). */
    suspend fun isDeviceRegistered(): Boolean {
        return userPreferences.isDeviceRegistered.first()
    }

    /** Get saved vendor ID for pre-filling the login screen after logout. */
    suspend fun getSavedVendorId(): String? {
        return userPreferences.vendorId.first()
    }

    // ── OTP Flow (first login) ──────────────────────────────────────────

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

                // Generate Keystore key pair and register with backend
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

        try {
            val response = authApi.registerDevice(
                RegisterDeviceRequest(deviceId = deviceId, publicKey = publicKeyPem)
            )
            if (response.isSuccessful) {
                userPreferences.setDeviceRegistered(true)
                Log.i(TAG, "Device registered successfully (deviceId=$deviceId, code=${response.code()})")
            } else {
                Log.w(TAG, "Device registration failed: ${response.code()} ${response.errorBody()?.string()}")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Device registration exception", e)
            // Will retry on next login
        }
    }

    // ── Device Attestation Flow (subsequent logins) ─────────────────────

    /**
     * Authenticate using StrongBox/TEE ECDSA signature instead of SMS OTP.
     * Flow: request challenge → sign with device key → send signed challenge.
     */
    suspend fun deviceLogin(vendorId: String): Resource<Unit> {
        val deviceId = getDeviceId()

        // Step 1: Request challenge nonce from backend
        val challengeResult = safeApiCall {
            authApi.requestChallenge(ChallengeRequest(vendorId = vendorId, deviceId = deviceId))
        }

        val challenge = when (challengeResult) {
            is Resource.Success -> challengeResult.data.challenge
            is Resource.Error -> {
                Log.w(TAG, "Challenge request failed: ${challengeResult.message} (code=${challengeResult.code})")
                // 403 = device not verified, fall back to OTP
                return Resource.Error(challengeResult.message, challengeResult.code)
            }
            is Resource.Loading -> return Resource.Loading
        }

        // Step 2: Sign the challenge with the device's ECDSA private key
        val signature = keystoreManager.sign(challenge.toByteArray(Charsets.UTF_8))
        if (signature == null) {
            Log.e(TAG, "Failed to sign challenge — keystore key unavailable")
            return Resource.Error("Device key unavailable. Please login with OTP.", 0)
        }

        // Step 3: Send signed challenge to backend
        val loginResult = safeApiCall {
            authApi.deviceLogin(
                DeviceLoginRequest(
                    vendorId = vendorId,
                    deviceId = deviceId,
                    challenge = challenge,
                    signature = signature
                )
            )
        }

        return when (loginResult) {
            is Resource.Success -> {
                val data = loginResult.data
                userPreferences.saveAuthData(data.accessToken, "")
                // Restore vendor info (phone might not be available in this flow)
                val savedPhone = userPreferences.phoneNumber.first() ?: ""
                userPreferences.saveVendorInfo(vendorId, savedPhone)
                Log.i(TAG, "Device login successful (vendorId=$vendorId)")
                Resource.Success(Unit)
            }
            is Resource.Error -> {
                Log.w(TAG, "Device login failed: ${loginResult.message} (code=${loginResult.code})")
                // 401 = signature mismatch, may need re-registration
                if (loginResult.code == 401) {
                    userPreferences.setDeviceRegistered(false)
                }
                Resource.Error(loginResult.message, loginResult.code)
            }
            is Resource.Loading -> Resource.Loading
        }
    }

    suspend fun logout() {
        // Atomic logout: clears auth token but preserves device_registered + vendor info
        // in a single DataStore transaction (avoids race condition with separate clear + re-set)
        userPreferences.clearForLogout()
    }
}
