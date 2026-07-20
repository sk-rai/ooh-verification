package com.trustcapture.vendor.domain.repository

import android.util.Log
import com.trustcapture.vendor.data.remote.api.CampaignApi
import com.trustcapture.vendor.data.remote.dto.AppConfigResponse
import com.trustcapture.vendor.data.remote.dto.CaptureConfig
import com.trustcapture.vendor.data.remote.dto.CampaignCaptureConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

private const val TAG = "AppConfigRepository"

/**
 * Fetches and caches app configuration from the backend.
 * All capture/upload/UI behavior is driven by this config.
 * Falls back to sensible defaults if the endpoint is unavailable.
 */
@Singleton
class AppConfigRepository @Inject constructor(
    private val campaignApi: CampaignApi
) {
    private val _config = MutableStateFlow(AppConfigResponse())
    val config: StateFlow<AppConfigResponse> = _config.asStateFlow()

    /** Fetch config from backend. Non-blocking — uses defaults on failure. */
    suspend fun refreshConfig() {
        try {
            val response = campaignApi.getAppConfig()
            if (response.isSuccessful && response.body() != null) {
                _config.value = response.body()!!
                Log.i(TAG, "App config loaded from backend")
            } else {
                Log.w(TAG, "Config endpoint returned ${response.code()}, using defaults")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Config fetch failed: ${e.message}, using defaults")
        }
    }

    /** Get effective capture config for a campaign (merges global + per-campaign overrides). */
    fun getEffectiveCaptureConfig(campaignOverride: CampaignCaptureConfig? = null): CaptureConfig {
        val global = _config.value.captureConfig
        if (campaignOverride == null) return global

        return global.copy(
            photoEnabled = campaignOverride.photoEnabled ?: global.photoEnabled,
            videoEnabled = campaignOverride.videoEnabled ?: global.videoEnabled,
            voiceNoteEnabled = campaignOverride.voiceNoteEnabled ?: global.voiceNoteEnabled,
            textNoteEnabled = campaignOverride.textNoteEnabled ?: global.textNoteEnabled,
            maxVideoDurationSeconds = campaignOverride.maxVideoDurationSeconds ?: global.maxVideoDurationSeconds,
            maxVideosPerLocation = campaignOverride.maxVideosPerLocation ?: global.maxVideosPerLocation,
            maxPhotosPerLocation = campaignOverride.maxPhotosPerLocation ?: global.maxPhotosPerLocation
        )
    }
}
