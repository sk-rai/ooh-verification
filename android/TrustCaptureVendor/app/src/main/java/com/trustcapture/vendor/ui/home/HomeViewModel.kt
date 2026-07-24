package com.trustcapture.vendor.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trustcapture.vendor.data.remote.UploadManager
import com.trustcapture.vendor.domain.repository.AppConfigRepository
import com.trustcapture.vendor.domain.repository.AuthRepository
import com.trustcapture.vendor.domain.repository.CampaignRepository
import com.trustcapture.vendor.domain.repository.PhotoRepository
import com.trustcapture.vendor.util.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HomeUiState(
    val hasCampaigns: Boolean = true,
    val quickCaptureEnabled: Boolean = true,
    val pendingUploads: Int = 0
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val campaignRepository: CampaignRepository,
    private val photoRepository: PhotoRepository,
    private val uploadManager: UploadManager,
    private val appConfigRepository: AppConfigRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {
        // Fetch app config
        viewModelScope.launch {
            appConfigRepository.refreshConfig()
            val config = appConfigRepository.config.value
            _uiState.value = _uiState.value.copy(
                quickCaptureEnabled = config.uiConfig.quickCaptureEnabled
            )
        }

        // Check if vendor has campaigns
        viewModelScope.launch {
            when (val result = campaignRepository.refreshCampaigns()) {
                is Resource.Success -> {
                    val campaigns = campaignRepository.getCachedCampaigns()
                    campaigns.collect { list ->
                        _uiState.value = _uiState.value.copy(hasCampaigns = list.isNotEmpty())
                    }
                }
                is Resource.Error -> {
                    // If can't fetch, assume has campaigns (show both options)
                    _uiState.value = _uiState.value.copy(hasCampaigns = true)
                }
                is Resource.Loading -> {}
            }
        }

        // Track pending uploads
        viewModelScope.launch {
            photoRepository.getPendingCount().collect { count ->
                _uiState.value = _uiState.value.copy(pendingUploads = count)
            }
        }

        // Trigger upload queue
        uploadManager.processQueue()
    }

    fun logout(onLoggedOut: () -> Unit) {
        viewModelScope.launch {
            authRepository.logout()
            onLoggedOut()
        }
    }
}
