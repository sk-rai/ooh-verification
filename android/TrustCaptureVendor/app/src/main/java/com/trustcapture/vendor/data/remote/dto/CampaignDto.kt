package com.trustcapture.vendor.data.remote.dto

import com.google.gson.annotations.SerializedName

data class CampaignListResponse(
    @SerializedName("campaigns") val campaigns: List<CampaignResponse>,
    @SerializedName("total") val total: Int
)

data class CampaignResponse(
    @SerializedName("campaign_id") val campaignId: String,
    @SerializedName("campaign_code") val campaignCode: String,
    @SerializedName("name") val name: String,
    @SerializedName("campaign_type") val campaignType: String,
    @SerializedName("status") val status: String,
    @SerializedName("start_date") val startDate: String,
    @SerializedName("end_date") val endDate: String,
    @SerializedName("assigned_at") val assignedAt: String?,
    @SerializedName("assignment_address") val assignmentAddress: String?,
    @SerializedName("assignment_latitude") val assignmentLatitude: Double?,
    @SerializedName("assignment_longitude") val assignmentLongitude: Double?,
    @SerializedName("assignment_location_name") val assignmentLocationName: String?,
    @SerializedName("location_profile") val locationProfile: LocationProfileResponse?,
    @SerializedName("created_at") val createdAt: String?
)

data class LocationProfileResponse(
    @SerializedName("expected_latitude") val expectedLatitude: Double?,
    @SerializedName("expected_longitude") val expectedLongitude: Double?,
    @SerializedName("tolerance_meters") val toleranceMeters: Double?,
    @SerializedName("expected_wifi_bssids") val expectedWifiBssids: List<String>?,
    @SerializedName("expected_cell_tower_ids") val expectedCellTowerIds: List<Int>?,
    @SerializedName("expected_pressure_min") val expectedPressureMin: Double?,
    @SerializedName("expected_pressure_max") val expectedPressureMax: Double?,
    @SerializedName("expected_light_min") val expectedLightMin: Double?,
    @SerializedName("expected_light_max") val expectedLightMax: Double?
)

data class PhotoUploadResponse(
    @SerializedName("photo_id") val photoId: String,
    @SerializedName("verification_status") val verificationStatus: String,
    @SerializedName("signature_valid") val signatureValid: Boolean?,
    @SerializedName("location_match_score") val locationMatchScore: Double?,
    @SerializedName("distance_from_expected") val distanceFromExpected: Double?,
    @SerializedName("s3_url") val s3Url: String?,
    @SerializedName("thumbnail_url") val thumbnailUrl: String?,
    @SerializedName("message") val message: String?
)
