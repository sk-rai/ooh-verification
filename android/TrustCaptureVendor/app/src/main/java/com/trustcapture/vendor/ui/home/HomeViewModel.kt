package com.trustcapture.vendor.ui.home

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trustcapture.vendor.data.local.datastore.UserPreferences
import com.trustcapture.vendor.data.remote.UploadManager
import com.trustcapture.vendor.domain.repository.AppConfigRepository
import com.trustcapture.vendor.domain.repository.AuthRepository
import com.trustcapture.vendor.domain.repository.CampaignRepository
import com.trustcapture.vendor.domain.repository.PhotoRepository
import com.trustcapture.vendor.service.TrackingSyncWorker
import com.trustcapture.vendor.util.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HomeUiState(
    val hasCampaigns: Boolean = true,
    val quickCaptureEnabled: Boolean = true,
    val showCampaigns: Boolean = true,
    val showSettings: Boolean = true,
    val maintenanceEnabled: Boolean = false,
    val maintenanceMessage: String = "",
    val tenantName: String = "TrustCapture",
    val pendingUploads: Int = 0,
    val trackingEnabled: Boolean = false,
    val showBackgroundLocationDialog: Boolean = false,
    val backgroundLocationGranted: Boolean = false
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val campaignRepository: CampaignRepository,
    private val photoRepository: PhotoRepository,
    private val uploadManager: UploadManager,
    private val appConfigRepository: AppConfigRepository,
    private val userPreferences: UserPreferences,
    private val application: Application
) : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {
        // Fetch app config
        viewModelScope.launch {
            appConfigRepository.refreshConfig()
            val config = appConfigRepository.config.value
            _uiState.value = _uiState.value.copy(
                quickCaptureEnabled = config.uiConfig.features.quickCapture,
                showCampaigns = config.uiConfig.features.campaigns,
                showSettings = config.uiConfig.features.settings,
                maintenanceEnabled = config.uiConfig.maintenance.enabled,
                maintenanceMessage = config.uiConfig.maintenance.message,
                tenantName = config.branding.tenantName,
                trackingEnabled = config.trackingConfig.enabled
            )

            // Handle tracking setup
            if (config.trackingConfig.enabled) {
                initializeTracking(config.trackingConfig.syncIntervalMinutes)
            }
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

    private suspend fun initializeTracking(syncIntervalMinutes: Int) {
        val alreadyPrompted = userPreferences.hasBeenPromptedForBackgroundLocation.first()
        if (!alreadyPrompted) {
            // Show dialog to ask for background location
            _uiState.value = _uiState.value.copy(showBackgroundLocationDialog = true)
        }
        // Schedule sync worker regardless — it will sync whatever points are collected
        TrackingSyncWorker.schedule(application, syncIntervalMinutes)
    }

    /**
     * Called when the user responds to the background location permission dialog.
     * If granted, the HomeScreen composable will start the TrackingService.
     */
    fun onBackgroundLocationPermissionResult(granted: Boolean) {
        viewModelScope.launch {
            userPreferences.setBackgroundLocationPrompted(true)
            _uiState.value = _uiState.value.copy(
                showBackgroundLocationDialog = false,
                backgroundLocationGranted = granted
            )
        }
    }

    /** Dismiss the dialog without granting */
    fun dismissBackgroundLocationDialog() {
        viewModelScope.launch {
            userPreferences.setBackgroundLocationPrompted(true)
            _uiState.value = _uiState.value.copy(showBackgroundLocationDialog = false)
        }
    }

    fun logout(onLoggedOut: () -> Unit) {
        viewModelScope.launch {
            authRepository.logout()
            onLoggedOut()
        }
    }
}
