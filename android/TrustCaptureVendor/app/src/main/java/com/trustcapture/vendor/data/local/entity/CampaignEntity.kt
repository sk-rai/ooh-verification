package com.trustcapture.vendor.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "campaigns")
data class CampaignEntity(
    @PrimaryKey val campaignId: String,
    val campaignCode: String,
    val name: String,
    val campaignType: String,
    val startDate: String,
    val endDate: String,
    val status: String
)
