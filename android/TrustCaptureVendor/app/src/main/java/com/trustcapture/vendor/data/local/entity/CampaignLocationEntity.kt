package com.trustcapture.vendor.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "campaign_locations")
data class CampaignLocationEntity(
    @PrimaryKey val profileId: String,
    val campaignId: String,
    val expectedLatitude: Double,
    val expectedLongitude: Double,
    val toleranceMeters: Int = 100,
    val resolvedAddress: String? = null
)
