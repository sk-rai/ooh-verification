package com.trustcapture.vendor.domain.repository

import com.trustcapture.vendor.data.local.db.CampaignDao
import com.trustcapture.vendor.data.local.entity.CampaignEntity
import com.trustcapture.vendor.data.local.entity.CampaignLocationEntity
import com.trustcapture.vendor.data.remote.api.CampaignApi
import com.trustcapture.vendor.util.Resource
import com.trustcapture.vendor.util.safeApiCall
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CampaignRepository @Inject constructor(
    private val campaignApi: CampaignApi,
    private val campaignDao: CampaignDao
) {
    private val _hasCampaigns = kotlinx.coroutines.flow.MutableStateFlow(false)
    val hasCampaigns: kotlinx.coroutines.flow.StateFlow<Boolean> = _hasCampaigns.asStateFlow()

    fun getCachedCampaigns(): Flow<List<CampaignEntity>> = campaignDao.getAllCampaigns()

    fun getLocationsForCampaign(campaignId: String): Flow<List<CampaignLocationEntity>> =
        campaignDao.getLocationsForCampaign(campaignId)

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
                        status = dto.status,
                        locationCount = dto.locations?.size ?: dto.locationCount ?: 0
                    )
                }
                campaignDao.deleteAll()
                campaignDao.deleteAllLocations()
                campaignDao.insertAll(entities)
                _hasCampaigns.value = result.data.hasCampaigns

                // Store locations for each campaign
                for (dto in result.data.campaigns) {
                    dto.locations?.let { locations ->
                        val locationEntities = locations.map { loc ->
                            CampaignLocationEntity(
                                profileId = loc.profileId,
                                campaignId = dto.campaignId,
                                expectedLatitude = loc.expectedLatitude,
                                expectedLongitude = loc.expectedLongitude,
                                toleranceMeters = loc.toleranceMeters,
                                resolvedAddress = loc.resolvedAddress
                            )
                        }
                        campaignDao.insertLocations(locationEntities)
                    }
                }

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
