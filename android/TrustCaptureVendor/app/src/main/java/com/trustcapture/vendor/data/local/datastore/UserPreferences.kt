package com.trustcapture.vendor.data.local.datastore

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
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
    }

    val authToken: Flow<String?> = dataStore.data.map { it[KEY_AUTH_TOKEN] }
    val tenantId: Flow<String?> = dataStore.data.map { it[KEY_TENANT_ID] }
    val vendorId: Flow<String?> = dataStore.data.map { it[KEY_VENDOR_ID] }
    val phoneNumber: Flow<String?> = dataStore.data.map { it[KEY_PHONE_NUMBER] }

    val isLoggedIn: Flow<Boolean> = authToken.map { !it.isNullOrBlank() }

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

    suspend fun clear() {
        dataStore.edit { it.clear() }
    }
}
