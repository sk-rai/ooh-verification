package com.trustcapture.vendor.ui.campaigns

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trustcapture.vendor.data.local.entity.CampaignEntity
import com.trustcapture.vendor.data.remote.UploadManager
import com.trustcapture.vendor.domain.repository.AuthRepository
import com.trustcapture.vendor.domain.repository.CampaignRepository
import com.trustcapture.vendor.domain.repository.PhotoRepository
import com.trustcapture.vendor.domain.validator.CampaignValidator
import com.trustcapture.vendor.util.DbDebugHelper
import com.trustcapture.vendor.util.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CampaignsUiState(
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val campaignCodeInput: String = "",
    val isValidating: Boolean = false,
    val validationError: String? = null,
    val validatedCampaignId: String? = null,
    val validatedCampaignCode: String? = null
)

@HiltViewModel
class CampaignsViewModel @Inject constructor(
    private val campaignRepository: CampaignRepository,
    private val authRepository: AuthRepository,
    private val photoRepository: PhotoRepository,
    private val uploadManager: UploadManager,
    private val campaignValidator: CampaignValidator,
    private val dbDebugHelper: DbDebugHelper
) : ViewModel() {

    private val _uiState = MutableStateFlow(CampaignsUiState())
    val uiState: StateFlow<CampaignsUiState> = _uiState.asStateFlow()

    val campaigns: StateFlow<List<CampaignEntity>> = campaignRepository
        .getCachedCampaigns()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val pendingUploadCount: StateFlow<Int> = photoRepository
        .getPendingCount()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), 0)

    init {
        refresh()
        // Try to upload any pending photos when campaigns screen loads
        uploadManager.processQueue()
        // Dump DB contents to logcat for debugging
        viewModelScope.launch { dbDebugHelper.dumpToLogcat() }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
            when (val result = campaignRepository.refreshCampaigns()) {
                is Resource.Success -> {
                    _uiState.value = _uiState.value.copy(isRefreshing = false)
                }
                is Resource.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isRefreshing = false,
                        error = result.message
                    )
                    // Seed demo data if DB is empty and API fails
                    seedDemoDataIfEmpty()
                }
                is Resource.Loading -> {}
            }
        }
    }

    private suspend fun seedDemoDataIfEmpty() {
        val current = campaigns.value
        if (current.isEmpty()) {
            val demoCampaigns = listOf(
                CampaignEntity("demo-1", "OOH2026A", "Highway Billboard Q1", "OOH", "2026-03-01", "2026-06-30", "active"),
                CampaignEntity("demo-2", "CON2026B", "Site Progress - Tower A", "Construction", "2026-02-15", "2026-12-31", "active"),
                CampaignEntity("demo-3", "INS2026C", "Vehicle Damage Claims", "Insurance", "2026-01-01", "2026-03-31", "completed")
            )
            campaignRepository.seedCampaigns(demoCampaigns)
        }
    }

    fun logout(onLoggedOut: () -> Unit) {
        viewModelScope.launch {
            authRepository.logout()
            onLoggedOut()
        }
    }

    fun onCampaignCodeChanged(code: String) {
        _uiState.value = _uiState.value.copy(
            campaignCodeInput = code,
            validationError = null,
            validatedCampaignId = null,
            validatedCampaignCode = null
        )
    }

    fun validateAndOpenCampaign(onValid: (campaignId: String, campaignCode: String, campaignType: String) -> Unit) {
        val code = _uiState.value.campaignCodeInput.trim()
        if (code.isEmpty()) {
            _uiState.value = _uiState.value.copy(validationError = "Enter a campaign code")
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isValidating = true, validationError = null)
            when (val result = campaignValidator.validate(code)) {
                is Resource.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isValidating = false,
                        campaignCodeInput = ""
                    )
                    onValid(result.data.campaignId, result.data.campaignCode, result.data.campaignType)
                }
                is Resource.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isValidating = false,
                        validationError = result.message
                    )
                }
                is Resource.Loading -> {}
            }
        }
    }
}
