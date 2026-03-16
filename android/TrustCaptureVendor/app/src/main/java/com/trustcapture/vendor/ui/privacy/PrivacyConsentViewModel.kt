package com.trustcapture.vendor.ui.privacy

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trustcapture.vendor.data.local.datastore.UserPreferences
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class PrivacyConsentViewModel @Inject constructor(
    private val userPreferences: UserPreferences
) : ViewModel() {

    private val _isSaving = MutableStateFlow(false)
    val isSaving: StateFlow<Boolean> = _isSaving.asStateFlow()

    fun saveConsent(locationConsent: Boolean, onDone: () -> Unit) {
        viewModelScope.launch {
            _isSaving.value = true
            userPreferences.saveConsent(
                privacyConsent = true,
                locationConsent = locationConsent
            )
            _isSaving.value = false
            onDone()
        }
    }
}
