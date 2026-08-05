package com.trustcapture.vendor.data.remote.dto

import com.google.gson.annotations.SerializedName

/**
 * Response from GET /api/app/config
 * Controls all app behavior — the Android app reads this on startup
 * and adjusts its UI/capture/upload behavior accordingly.
 */
data class AppConfigResponse(
    @SerializedName("capture_config") val captureConfig: CaptureConfig = CaptureConfig(),
    @SerializedName("upload_config") val uploadConfig: UploadConfig = UploadConfig(),
    @SerializedName("ui_config") val uiConfig: UiConfig = UiConfig(),
    @SerializedName("branding") val branding: BrandingConfig = BrandingConfig(),
    @SerializedName("version") val version: VersionConfig = VersionConfig(),
    @SerializedName("tracking_config") val trackingConfig: TrackingConfig = TrackingConfig()
)

data class CaptureConfig(
    @SerializedName("photo_enabled") val photoEnabled: Boolean = true,
    @SerializedName("video_enabled") val videoEnabled: Boolean = true,
    @SerializedName("voice_note_enabled") val voiceNoteEnabled: Boolean = true,
    @SerializedName("text_note_enabled") val textNoteEnabled: Boolean = true,
    @SerializedName("max_video_duration_seconds") val maxVideoDurationSeconds: Int = 60,
    @SerializedName("max_voice_duration_seconds") val maxVoiceDurationSeconds: Int = 120,
    @SerializedName("max_photos_per_location") val maxPhotosPerLocation: Int = 10,
    @SerializedName("max_videos_per_location") val maxVideosPerLocation: Int = 5,
    @SerializedName("max_voice_notes_per_location") val maxVoiceNotesPerLocation: Int = 5,
    @SerializedName("video_resolution") val videoResolution: String = "720p",
    @SerializedName("photo_max_dimension") val photoMaxDimension: Int = 3000,
    @SerializedName("photo_compression_quality") val photoCompressionQuality: Int = 90,
    @SerializedName("watermark_enabled") val watermarkEnabled: Boolean = true,
    @SerializedName("watermark_opacity") val watermarkOpacity: Int = 160,
    @SerializedName("watermark_height_percent") val watermarkHeightPercent: Int = 15,
    @SerializedName("compass_enabled") val compassEnabled: Boolean = true,
    @SerializedName("gallery_upload_allowed") val galleryUploadAllowed: Boolean = false,
    @SerializedName("gps_required") val gpsRequired: Boolean = true,
    @SerializedName("gps_min_accuracy_meters") val gpsMinAccuracyMeters: Int = 50,
    @SerializedName("gps_timeout_seconds") val gpsTimeoutSeconds: Int = 30,
    @SerializedName("gps_interval_high_ms") val gpsIntervalHighMs: Long = 5000L,
    @SerializedName("gps_interval_balanced_ms") val gpsIntervalBalancedMs: Long = 15000L,
    @SerializedName("camera_facing") val cameraFacing: String = "back",
    @SerializedName("allow_emulator_capture") val allowEmulatorCapture: Boolean = true,
    @SerializedName("allow_rooted_capture") val allowRootedCapture: Boolean = true,
    @SerializedName("max_text_note_length") val maxTextNoteLength: Int = 500
)

data class UploadConfig(
    @SerializedName("endpoint") val endpoint: String = "/api/evidence/upload",
    @SerializedName("max_file_size_mb") val maxFileSizeMb: Int = 50,
    @SerializedName("retry_max_attempts") val retryMaxAttempts: Int = 5,
    @SerializedName("background_upload") val backgroundUpload: Boolean = true,
    @SerializedName("wifi_only_upload") val wifiOnlyUpload: Boolean = false,
    @SerializedName("upload_timeout_photo_ms") val uploadTimeoutPhotoMs: Long = 60_000L,
    @SerializedName("upload_timeout_video_ms") val uploadTimeoutVideoMs: Long = 120_000L,
    @SerializedName("upload_periodic_interval_minutes") val uploadPeriodicIntervalMinutes: Long = 15L
)

data class UiConfig(
    @SerializedName("quick_capture_enabled") val quickCaptureEnabled: Boolean = true,
    @SerializedName("categories") val categories: List<String> = listOf(
        "accident", "damage", "inspection", "delivery_proof", "hazard", "other"
    ),
    @SerializedName("show_confidence_score") val showConfidenceScore: Boolean = true,
    @SerializedName("show_sensor_details") val showSensorDetails: Boolean = true,
    @SerializedName("features") val features: FeaturesConfig = FeaturesConfig(),
    @SerializedName("maintenance") val maintenance: MaintenanceConfig = MaintenanceConfig()
)

data class FeaturesConfig(
    @SerializedName("campaigns") val campaigns: Boolean = true,
    @SerializedName("quick_capture") val quickCapture: Boolean = true,
    @SerializedName("settings") val settings: Boolean = true,
    @SerializedName("tracking") val tracking: Boolean = false
)

data class MaintenanceConfig(
    @SerializedName("enabled") val enabled: Boolean = false,
    @SerializedName("message") val message: String = ""
)

data class TrackingConfig(
    @SerializedName("enabled") val enabled: Boolean = false,
    @SerializedName("interval_minutes") val intervalMinutes: Int = 30,
    @SerializedName("max_duration_hours") val maxDurationHours: Int = 8,
    @SerializedName("sync_interval_minutes") val syncIntervalMinutes: Int = 30,
    @SerializedName("min_accuracy_meters") val minAccuracyMeters: Int = 100,
    @SerializedName("stop_on_app_close") val stopOnAppClose: Boolean = true,
    @SerializedName("collect_battery_level") val collectBatteryLevel: Boolean = true
)

data class BrandingConfig(
    @SerializedName("primary_color") val primaryColor: String = "#3B82F6",
    @SerializedName("secondary_color") val secondaryColor: String = "#10B981",
    @SerializedName("tenant_name") val tenantName: String = "TrustCapture",
    @SerializedName("logo_url") val logoUrl: String? = null,
    @SerializedName("watermark_text") val watermarkText: String = "TrustCapture"
)

data class VersionConfig(
    @SerializedName("latest_version_code") val latestVersionCode: Int = 11,
    @SerializedName("latest_version_name") val latestVersionName: String = "1.3.0",
    @SerializedName("min_supported_version") val minSupportedVersion: Int = 8,
    @SerializedName("update_url") val updateUrl: String = "https://play.google.com/store/apps/details?id=com.lynksavvy.trustcapture",
    @SerializedName("message") val message: String? = null
)

/**
 * Per-campaign config override (returned in campaigns endpoint).
 * Null fields mean "use global config".
 */
data class CampaignCaptureConfig(
    @SerializedName("max_video_duration_seconds") val maxVideoDurationSeconds: Int? = null,
    @SerializedName("max_videos_per_location") val maxVideosPerLocation: Int? = null,
    @SerializedName("max_photos_per_location") val maxPhotosPerLocation: Int? = null,
    @SerializedName("photo_enabled") val photoEnabled: Boolean? = null,
    @SerializedName("video_enabled") val videoEnabled: Boolean? = null,
    @SerializedName("voice_note_enabled") val voiceNoteEnabled: Boolean? = null,
    @SerializedName("text_note_enabled") val textNoteEnabled: Boolean? = null,
    @SerializedName("categories") val categories: List<String>? = null
)
