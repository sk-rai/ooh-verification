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
    val error: String? = null
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    fun onVendorIdChange(value: String) {
        _uiState.value = _uiState.value.copy(
            vendorId = value.uppercase().take(6),
            error = null
        )
    }

    fun onPhoneNumberChange(value: String) {
        _uiState.value = _uiState.value.copy(
            phoneNumber = value.filter { it.isDigit() || it == '+' }.take(15),
            error = null
        )
    }

    fun requestOtp(onSuccess: () -> Unit) {
        val state = _uiState.value
        if (state.vendorId.length < 6) {
            _uiState.value = state.copy(error = "Vendor ID must be 6 characters")
            return
        }
        if (state.phoneNumber.length < 10) {
            _uiState.value = state.copy(error = "Enter a valid phone number")
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = authRepository.requestOtp(state.phoneNumber, state.vendorId)) {
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
