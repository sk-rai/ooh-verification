package com.trustcapture.vendor.domain.repository

import com.trustcapture.vendor.data.local.db.CampaignDao
import com.trustcapture.vendor.data.local.entity.CampaignEntity
import com.trustcapture.vendor.data.remote.api.CampaignApi
import com.trustcapture.vendor.util.Resource
import com.trustcapture.vendor.util.safeApiCall
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CampaignRepository @Inject constructor(
    private val campaignApi: CampaignApi,
    private val campaignDao: CampaignDao
) {
    fun getCachedCampaigns(): Flow<List<CampaignEntity>> = campaignDao.getAllCampaigns()

    suspend fun refreshCampaigns(): Resource<Unit> {
        val result = safeApiCall { campaignApi.getAssignedCampaigns() }
        return when (result) {
            is Resource.Success -> {
                val entities = result.data.campaigns.map { dto ->
                    CampaignEntity(
                        campaignId = dto.campaignId,
                        campaignCode = dto.campaignCode,
                        name = dto.name,
                        campaignType = dto.campaignType,
                        startDate = dto.startDate,
                        endDate = dto.endDate,
                        status = dto.status
                    )
                }
                campaignDao.deleteAll()
                campaignDao.insertAll(entities)
                Resource.Success(Unit)
            }
            is Resource.Error -> Resource.Error(result.message, result.code)
            is Resource.Loading -> Resource.Loading
        }
    }

    suspend fun seedCampaigns(campaigns: List<CampaignEntity>) {
        campaignDao.insertAll(campaigns)
    }
}
