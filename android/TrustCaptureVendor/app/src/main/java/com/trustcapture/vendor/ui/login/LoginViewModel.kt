package com.trustcapture.vendor.ui.login

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

data class LoginUiState(
    val vendorId: String = "",
    val phoneNumber: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
    val isDeviceRegistered: Boolean = false
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            val registered = authRepository.isDeviceRegistered()
            val savedVendorId = authRepository.getSavedVendorId()
            _uiState.value = _uiState.value.copy(
                isDeviceRegistered = registered,
                vendorId = savedVendorId ?: ""
            )
        }
    }

    fun onVendorIdChange(value: String) {
        _uiState.value = _uiState.value.copy(
            vendorId = value.uppercase().take(6),
            error = null
        )
    }

    fun onPhoneNumberChange(value: String) {
        _uiState.value = _uiState.value.copy(
            phoneNumber = value.filter { it.isDigit() }.take(10),
            error = null
        )
    }

    /**
     * Smart login: tries device attestation first if registered,
     * falls back to OTP flow if not registered or attestation fails.
     */
    fun login(onOtpNeeded: () -> Unit, onLoggedIn: () -> Unit) {
        val state = _uiState.value
        if (state.vendorId.length < 6) {
            _uiState.value = state.copy(error = "Vendor ID must be 6 characters")
            return
        }

        if (state.isDeviceRegistered) {
            // Try device attestation (no SMS needed)
            attemptDeviceLogin(onFallbackToOtp = {
                // Device login failed — fall back to OTP
                requestOtp(onOtpNeeded)
            }, onSuccess = onLoggedIn)
        } else {
            // First login — need OTP
            if (state.phoneNumber.length < 10) {
                _uiState.value = state.copy(error = "Enter a valid 10-digit phone number")
                return
            }
            requestOtp(onOtpNeeded)
        }
    }

    private fun attemptDeviceLogin(onFallbackToOtp: () -> Unit, onSuccess: () -> Unit) {
        val vendorId = _uiState.value.vendorId
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = authRepository.deviceLogin(vendorId)) {
                is Resource.Success -> {
                    _uiState.value = _uiState.value.copy(isLoading = false)
                    onSuccess()
                }
                is Resource.Error -> {
                    _uiState.value = _uiState.value.copy(isLoading = false)
                    // 403 = device not verified, 401 = key mismatch → fall back to OTP
                    if (result.code == 403 || result.code == 401) {
                        _uiState.value = _uiState.value.copy(
                            isDeviceRegistered = false,
                            error = "Device auth failed. Please verify with OTP."
                        )
                        onFallbackToOtp()
                    } else {
                        _uiState.value = _uiState.value.copy(error = result.message)
                    }
                }
                is Resource.Loading -> {}
            }
        }
    }

    fun requestOtp(onSuccess: () -> Unit) {
        val state = _uiState.value
        if (state.vendorId.length < 6) {
            _uiState.value = state.copy(error = "Vendor ID must be 6 characters")
            return
        }
        if (state.phoneNumber.length < 10) {
            _uiState.value = state.copy(error = "Enter a valid 10-digit phone number")
            return
        }

        val fullPhone = "+91${state.phoneNumber}"

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = authRepository.requestOtp(fullPhone, state.vendorId)) {
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

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
