package com.trustcapture.vendor.ui.login

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.trustcapture.vendor.domain.repository.AuthRepository
import com.trustcapture.vendor.util.CountryCodeHelper
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
    val countryCode: String = "+1",
    val isLoading: Boolean = false,
    val error: String? = null,
    val isDeviceRegistered: Boolean = false
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    application: Application,
    private val authRepository: AuthRepository
) : AndroidViewModel(application) {

    private val _uiState = MutableStateFlow(LoginUiState(
        countryCode = CountryCodeHelper.getDialCode(application)
    ))
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            val registered = authRepository.isDeviceRegistered()
            val savedVendorId = authRepository.getSavedVendorId()
            android.util.Log.d("LoginViewModel", "init: isDeviceRegistered=$registered, savedVendorId=$savedVendorId")
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
            phoneNumber = value.filter { it.isDigit() }.take(15),
            error = null
        )
    }

    fun onCountryCodeChange(value: String) {
        val filtered = value.filter { it.isDigit() || it == '+' }.take(5)
        _uiState.value = _uiState.value.copy(
            countryCode = if (filtered.startsWith("+")) filtered else "+$filtered",
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
            attemptDeviceLogin(onFallbackToOtp = {
                requestOtp(onOtpNeeded)
            }, onSuccess = onLoggedIn)
        } else {
            if (state.phoneNumber.length < 7) {
                _uiState.value = state.copy(error = "Enter a valid phone number")
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

    /** Full phone number with country code for API calls. */
    private fun fullPhoneNumber(): String {
        val state = _uiState.value
        return "${state.countryCode}${state.phoneNumber}"
    }

    fun requestOtp(onSuccess: () -> Unit) {
        val state = _uiState.value
        if (state.vendorId.length < 6) {
            _uiState.value = state.copy(error = "Vendor ID must be 6 characters")
            return
        }
        if (state.phoneNumber.length < 7) {
            _uiState.value = state.copy(error = "Enter a valid phone number")
            return
        }

        val fullPhone = fullPhoneNumber()

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
