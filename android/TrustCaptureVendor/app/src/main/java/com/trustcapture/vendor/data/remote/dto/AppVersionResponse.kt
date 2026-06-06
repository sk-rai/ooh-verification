package com.trustcapture.vendor.data.remote.dto

import com.google.gson.annotations.SerializedName

/**
 * Response from GET /api/app/version-check?platform=android&current_version=5
 *
 * Backend returns:
 * - update_available: true/false
 * - force_update: true if current version is below minimum supported
 * - latest_version: the newest version code available
 * - latest_version_name: human-readable version (e.g., "1.2.0")
 * - update_url: Play Store URL for the app
 * - message: optional message to show the user
 */
data class AppVersionResponse(
    @SerializedName("update_available") val updateAvailable: Boolean = false,
    @SerializedName("force_update") val forceUpdate: Boolean = false,
    @SerializedName("latest_version") val latestVersion: Int = 0,
    @SerializedName("latest_version_name") val latestVersionName: String = "",
    @SerializedName("update_url") val updateUrl: String = "https://play.google.com/store/apps/details?id=com.lynksavvy.trustcapture",
    @SerializedName("message") val message: String? = null
)
