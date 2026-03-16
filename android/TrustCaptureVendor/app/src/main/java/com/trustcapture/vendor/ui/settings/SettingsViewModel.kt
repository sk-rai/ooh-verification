package com.trustcapture.vendor.ui.settings

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trustcapture.vendor.data.local.datastore.UserPreferences
import com.trustcapture.vendor.domain.gdpr.GdprManager
import com.trustcapture.vendor.domain.repository.AuthRepository
import com.trustcapture.vendor.domain.repository.PhotoRepository
import com.trustcapture.vendor.util.KeystoreManager
import com.trustcapture.vendor.util.SecurityManager
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

data class SettingsUiState(
    val vendorId: String = "",
    val phoneNumber: String = "",
    val deviceId: String = "",
    val publicKeyFingerprint: String = "",
    val appVersion: String = "1.0",
    val isEmulator: Boolean = false,
    val isRooted: Boolean = false,
    val securityFlags: List<String> = emptyList(),
    val cacheCleared: Boolean = false,
    val encryptedPhotosSize: String = "0 KB",
    // GDPR
    val privacyModeEnabled: Boolean = false,
    val isExporting: Boolean = false,
    val exportPath: String? = null,
    val isDeleting: Boolean = false
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val userPreferences: UserPreferences,
    private val authRepository: AuthRepository,
    private val photoRepository: PhotoRepository,
    private val keystoreManager: KeystoreManager,
    private val securityManager: SecurityManager,
    private val gdprManager: GdprManager,
    @ApplicationContext private val context: Context
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    val pendingUploadCount: StateFlow<Int> = photoRepository
        .getPendingCount()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), 0)

    init {
        loadSettings()
    }

    private fun loadSettings() {
        viewModelScope.launch {
            val vendorId = userPreferences.vendorId.first() ?: ""
            val phone = userPreferences.phoneNumber.first() ?: ""
            val privacyMode = userPreferences.privacyModeEnabled.first()
            val assessment = securityManager.assess()

            // Get public key fingerprint (first 16 chars of PEM hash)
            val pubKey = keystoreManager.getPublicKeyPem() ?: "Not registered"
            val fingerprint = if (pubKey != "Not registered") {
                pubKey.hashCode().toUInt().toString(16).uppercase().take(8)
            } else "N/A"

            // Calculate encrypted photos directory size
            val encDir = File(context.filesDir, "encrypted_photos")
            val sizeBytes = if (encDir.exists()) encDir.walkTopDown().sumOf { it.length() } else 0L
            val sizeStr = when {
                sizeBytes < 1024 -> "$sizeBytes B"
                sizeBytes < 1024 * 1024 -> "${sizeBytes / 1024} KB"
                else -> "${"%.1f".format(sizeBytes / (1024.0 * 1024.0))} MB"
            }

            val deviceId = android.provider.Settings.Secure.getString(
                context.contentResolver,
                android.provider.Settings.Secure.ANDROID_ID
            ) ?: ""

            _uiState.value = SettingsUiState(
                vendorId = vendorId,
                phoneNumber = phone,
                deviceId = deviceId,
                publicKeyFingerprint = fingerprint,
                appVersion = getAppVersion(),
                isEmulator = assessment.isEmulator,
                isRooted = assessment.isRooted,
                securityFlags = assessment.toAuditFlags(),
                encryptedPhotosSize = sizeStr,
                privacyModeEnabled = privacyMode
            )
        }
    }

    private fun getAppVersion(): String {
        return try {
            val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            "${pInfo.versionName} (${pInfo.longVersionCode})"
        } catch (_: Exception) { "1.0" }
    }

    fun clearCache() {
        viewModelScope.launch {
            // Clear uploaded photos from DB
            photoRepository.cleanupUploaded()
            // Clear image cache
            context.cacheDir.listFiles()?.forEach { it.delete() }
            _uiState.value = _uiState.value.copy(cacheCleared = true)
            // Refresh size
            loadSettings()
        }
    }

    fun logout(onLoggedOut: () -> Unit) {
        viewModelScope.launch {
            authRepository.logout()
            onLoggedOut()
        }
    }

    // ── GDPR Actions (Req 24.3, 24.4, 24.6) ──────────────────────────────

    fun togglePrivacyMode() {
        viewModelScope.launch {
            val newValue = !_uiState.value.privacyModeEnabled
            userPreferences.setPrivacyMode(newValue)
            _uiState.value = _uiState.value.copy(privacyModeEnabled = newValue)
        }
    }

    fun exportData() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isExporting = true, exportPath = null)
            try {
                val file = gdprManager.exportUserData()
                _uiState.value = _uiState.value.copy(isExporting = false, exportPath = file.absolutePath)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isExporting = false)
            }
        }
    }

    fun deleteAllData(onDeleted: () -> Unit) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isDeleting = true)
            gdprManager.deleteAllUserData()
            _uiState.value = _uiState.value.copy(isDeleting = false)
            onDeleted()
        }
    }
}
