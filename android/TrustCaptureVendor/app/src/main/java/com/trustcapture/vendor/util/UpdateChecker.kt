package com.trustcapture.vendor.util

import android.util.Log
import com.trustcapture.vendor.BuildConfig
import com.trustcapture.vendor.data.remote.api.CampaignApi
import com.trustcapture.vendor.data.remote.dto.AppVersionResponse
import javax.inject.Inject
import javax.inject.Singleton

private const val TAG = "UpdateChecker"

/**
 * Checks if a newer version of the app is available.
 * Called on app startup (Campaigns screen) — non-blocking.
 *
 * Returns null if the check fails (network error, backend not supporting this endpoint yet).
 * This ensures the app still works even if the endpoint isn't deployed.
 */
@Singleton
class UpdateChecker @Inject constructor(
    private val campaignApi: CampaignApi
) {
    suspend fun check(): AppVersionResponse? {
        return try {
            val response = campaignApi.checkAppVersion(
                platform = "android",
                currentVersion = BuildConfig.VERSION_CODE
            )
            if (response.isSuccessful) {
                response.body()
            } else {
                Log.w(TAG, "Version check returned ${response.code()}")
                null
            }
        } catch (e: Exception) {
            // Silently fail — don't block app usage if version check fails
            Log.w(TAG, "Version check failed: ${e.message}")
            null
        }
    }
}
