package com.trustcapture.vendor.data.local.datastore

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UserPreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>
) {
    companion object {
        private val KEY_AUTH_TOKEN = stringPreferencesKey("auth_token")
        private val KEY_TENANT_ID = stringPreferencesKey("tenant_id")
        private val KEY_VENDOR_ID = stringPreferencesKey("vendor_id")
        private val KEY_PHONE_NUMBER = stringPreferencesKey("phone_number")
        // GDPR consent flags (Req 24.1-24.7)
        private val KEY_PRIVACY_CONSENT = booleanPreferencesKey("privacy_consent")
        private val KEY_LOCATION_CONSENT = booleanPreferencesKey("location_consent")
        private val KEY_PRIVACY_MODE = booleanPreferencesKey("privacy_mode")
        private val KEY_DEVICE_REGISTERED = booleanPreferencesKey("device_registered")
    }

    val authToken: Flow<String?> = dataStore.data.map { it[KEY_AUTH_TOKEN] }
    val tenantId: Flow<String?> = dataStore.data.map { it[KEY_TENANT_ID] }
    val vendorId: Flow<String?> = dataStore.data.map { it[KEY_VENDOR_ID] }
    val phoneNumber: Flow<String?> = dataStore.data.map { it[KEY_PHONE_NUMBER] }

    val isLoggedIn: Flow<Boolean> = authToken.map { !it.isNullOrBlank() }

    // GDPR consent flows
    val hasPrivacyConsent: Flow<Boolean> = dataStore.data.map { it[KEY_PRIVACY_CONSENT] == true }
    val hasLocationConsent: Flow<Boolean> = dataStore.data.map { it[KEY_LOCATION_CONSENT] == true }
    val privacyModeEnabled: Flow<Boolean> = dataStore.data.map { it[KEY_PRIVACY_MODE] == true }
    val isDeviceRegistered: Flow<Boolean> = dataStore.data.map { it[KEY_DEVICE_REGISTERED] == true }

    suspend fun saveAuthData(token: String, tenantId: String) {
        dataStore.edit { prefs ->
            prefs[KEY_AUTH_TOKEN] = token
            prefs[KEY_TENANT_ID] = tenantId
        }
    }

    suspend fun saveVendorInfo(vendorId: String, phoneNumber: String) {
        dataStore.edit { prefs ->
            prefs[KEY_VENDOR_ID] = vendorId
            prefs[KEY_PHONE_NUMBER] = phoneNumber
        }
    }

    /** Save GDPR consent (Req 24.1, 24.2) */
    suspend fun saveConsent(privacyConsent: Boolean, locationConsent: Boolean) {
        dataStore.edit { prefs ->
            prefs[KEY_PRIVACY_CONSENT] = privacyConsent
            prefs[KEY_LOCATION_CONSENT] = locationConsent
        }
    }

    /** Toggle privacy mode — anonymizes vendor ID in exports (Req 24.6) */
    suspend fun setPrivacyMode(enabled: Boolean) {
        dataStore.edit { prefs ->
            prefs[KEY_PRIVACY_MODE] = enabled
        }
    }

    suspend fun setDeviceRegistered(registered: Boolean) {
        dataStore.edit { prefs ->
            prefs[KEY_DEVICE_REGISTERED] = registered
        }
    }

    suspend fun clear() {
        dataStore.edit { it.clear() }
    }
}
