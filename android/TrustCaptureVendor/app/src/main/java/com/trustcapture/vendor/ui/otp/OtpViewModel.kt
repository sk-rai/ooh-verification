package com.trustcapture.vendor.ui.otp

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trustcapture.vendor.domain.repository.AuthRepository
import com.trustcapture.vendor.util.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class OtpUiState(
    val otp: String = "",
    val phoneNumber: String = "",
    val vendorId: String = "",
    val isLoading: Boolean = false,
    val isResending: Boolean = false,
    val error: String? = null,
    val resendMessage: String? = null
)

@HiltViewModel
class OtpViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(
        OtpUiState(
            phoneNumber = savedStateHandle.get<String>("phoneNumber") ?: "",
            vendorId = savedStateHandle.get<String>("vendorId") ?: ""
        )
    )
    val uiState: StateFlow<OtpUiState> = _uiState.asStateFlow()

    fun onOtpChange(value: String) {
        _uiState.value = _uiState.value.copy(
            otp = value.filter { it.isDigit() }.take(6),
            error = null
        )
    }

    fun verifyOtp(onSuccess: () -> Unit) {
        val state = _uiState.value
        if (state.otp.length < 6) {
            _uiState.value = state.copy(error = "Enter the 6-digit OTP")
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = authRepository.verifyOtp(
                state.phoneNumber, state.vendorId, state.otp
            )) {
                is Resource.Success -> {
                    _uiState.value = _uiState.value.copy(isLoading = false)
                    onSuccess()
                }
                is Resource.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = result.message
                    )
                }
                is Resource.Loading -> {}
            }
        }
    }

    fun resendOtp() {
        val state = _uiState.value
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isResending = true, resendMessage = null)
            when (val result = authRepository.requestOtp(state.phoneNumber, state.vendorId)) {
                is Resource.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isResending = false,
                        resendMessage = "OTP sent again"
                    )
                }
                is Resource.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isResending = false,
                        error = result.message
                    )
                }
                is Resource.Loading -> {}
            }
        }
    }
}
