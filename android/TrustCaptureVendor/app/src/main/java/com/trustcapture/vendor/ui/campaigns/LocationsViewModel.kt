package com.trustcapture.vendor.ui.campaigns

import androidx.lifecycle.ViewModel
import com.trustcapture.vendor.data.local.entity.CampaignLocationEntity
import com.trustcapture.vendor.domain.repository.CampaignRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

@HiltViewModel
class LocationsViewModel @Inject constructor(
    private val campaignRepository: CampaignRepository
) : ViewModel() {

    fun getLocations(campaignId: String): Flow<List<CampaignLocationEntity>> =
        campaignRepository.getLocationsForCampaign(campaignId)
}
