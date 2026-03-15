package com.trustcapture.vendor.data.remote.api

import com.trustcapture.vendor.data.remote.dto.CampaignListResponse
import com.trustcapture.vendor.data.remote.dto.CampaignResponse
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path

interface CampaignApi {

    @GET("api/vendors/me/campaigns")
    suspend fun getAssignedCampaigns(): Response<CampaignListResponse>

    @GET("api/campaigns/{campaign_id}")
    suspend fun getCampaignById(
        @Path("campaign_id") campaignId: String
    ): Response<CampaignResponse>
}
