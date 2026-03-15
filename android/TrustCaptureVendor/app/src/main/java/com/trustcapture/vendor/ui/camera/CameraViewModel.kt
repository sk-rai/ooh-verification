package com.trustcapture.vendor.ui.camera

import android.content.Context
import android.net.Uri
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trustcapture.vendor.data.local.datastore.UserPreferences
import com.trustcapture.vendor.util.CellTowerData
import com.trustcapture.vendor.util.CellTowerEntryData
import com.trustcapture.vendor.util.CellTowerScanner
import com.trustcapture.vendor.util.EnvironmentalData
import com.trustcapture.vendor.util.EnvironmentalSensorData
import com.trustcapture.vendor.util.EnvironmentalSensors
import com.trustcapture.vendor.util.GpsData
import com.trustcapture.vendor.util.LocationTriangulator
import com.trustcapture.vendor.util.MagneticFieldData
import com.trustcapture.vendor.util.PhotoSigner
import com.trustcapture.vendor.util.SensorDataSnapshot
import com.trustcapture.vendor.util.WatermarkData
import com.trustcapture.vendor.util.WatermarkGenerator
import com.trustcapture.vendor.util.WifiData
import com.trustcapture.vendor.util.WifiNetworkData
import com.trustcapture.vendor.util.WifiScanner
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Date
import javax.inject.Inject

enum class CameraScreenState {
    PREVIEW, PROCESSING, CAPTURED, UPLOADING
}

data class CameraUiState(
    val campaignId: String = "",
    val campaignCode: String = "",
    val screenState: CameraScreenState = CameraScreenState.PREVIEW,
    val originalPhotoUri: Uri? = null,
    val watermarkedPhotoUri: Uri? = null,
    val signatureJson: String? = null,
    val sensorDataJson: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val accuracy: Float? = null,
    val altitude: Double? = null,
    val gpsStatus: String = "Acquiring GPS...",
    // Environmental sensors
    val pressureHpa: Float? = null,
    val lightLux: Float? = null,
    val magneticMagnitude: Float? = null,
    val tremorDetected: Boolean = false,
    val environmentalData: EnvironmentalData? = null,
    // WiFi
    val wifiCount: Int = 0,
    // Cell towers
    val cellTowerCount: Int = 0,
    // Triangulation
    val confidenceScore: Int? = null,
    val triangulationFlags: List<String> = emptyList(),
    val sensorSummary: String = "Sensors: loading...",
    val isUploading: Boolean = false,
    val uploadProgress: Float = 0f,
    val error: String? = null,
    val uploadSuccess: Boolean = false
)

@HiltViewModel
class CameraViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val userPreferences: UserPreferences,
    private val photoSigner: PhotoSigner,
    private val environmentalSensors: EnvironmentalSensors,
    private val wifiScanner: WifiScanner,
    private val cellTowerScanner: CellTowerScanner,
    private val locationTriangulator: LocationTriangulator,
    @ApplicationContext private val appContext: Context
) : ViewModel() {

    private val _uiState = MutableStateFlow(
        CameraUiState(
            campaignId = savedStateHandle.get<String>("campaignId") ?: "",
            campaignCode = savedStateHandle.get<String>("campaignCode") ?: ""
        )
    )
    val uiState: StateFlow<CameraUiState> = _uiState.asStateFlow()

    init {
        // Start collecting environmental sensor data
        viewModelScope.launch {
            environmentalSensors.observe(appContext).collect { env ->
                _uiState.value = _uiState.value.copy(
                    pressureHpa = env.pressureHpa,
                    lightLux = env.lightLux,
                    magneticMagnitude = env.magneticMagnitude,
                    tremorDetected = env.tremorDetected,
                    environmentalData = env,
                    sensorSummary = buildSensorSummary(env)
                )
            }
        }
        // Trigger a WiFi scan
        viewModelScope.launch {
            try {
                wifiScanner.scan(appContext).collect { result ->
                    _uiState.value = _uiState.value.copy(wifiCount = result.networks.size)
                }
            } catch (_: Exception) {
                // WiFi scan may fail on emulator — that's fine
            }
        }
    }

    private fun buildSensorSummary(env: EnvironmentalData): String {
        val parts = mutableListOf<String>()
        env.pressureHpa?.let { parts.add("${it.toInt()}hPa") }
        env.lightLux?.let { parts.add("${it.toInt()}lux") }
        env.magneticMagnitude?.let { parts.add("${it.toInt()}µT") }
        if (env.tremorDetected) parts.add("⚠tremor")
        return if (parts.isEmpty()) "Sensors: N/A" else parts.joinToString(" · ")
    }

    fun onPhotoCaptured(uri: Uri) {
        _uiState.value = _uiState.value.copy(
            screenState = CameraScreenState.PROCESSING,
            originalPhotoUri = uri
        )

        viewModelScope.launch {
            val vendorId = userPreferences.vendorId.first() ?: "UNKNOWN"
            val state = _uiState.value

            val watermarkData = WatermarkData(
                latitude = state.latitude,
                longitude = state.longitude,
                accuracy = state.accuracy,
                campaignCode = state.campaignCode,
                vendorId = vendorId
            )

            val watermarkedUri = withContext(Dispatchers.IO) {
                WatermarkGenerator.applyWatermark(appContext, uri, watermarkData)
            }

            // Sign the watermarked photo with device Keystore key
            val finalUri = watermarkedUri ?: uri
            val signatureJson = withContext(Dispatchers.IO) {
                photoSigner.signPhoto(
                    context = appContext,
                    photoUri = finalUri,
                    latitude = state.latitude,
                    longitude = state.longitude
                )
            }

            // Build sensor data snapshot for upload
            val wifiResult = withContext(Dispatchers.IO) {
                wifiScanner.getLastResults(appContext)
            }
            val cellResult = withContext(Dispatchers.IO) {
                cellTowerScanner.scan(appContext)
            }
            val env = state.environmentalData
            val sensorSnapshot = SensorDataSnapshot(
                gps = if (state.latitude != null && state.longitude != null) {
                    GpsData(
                        latitude = state.latitude!!,
                        longitude = state.longitude!!,
                        accuracy = state.accuracy ?: 0f,
                        altitude = state.altitude
                    )
                } else null,
                wifi = WifiData(
                    networks = wifiResult.networks.map { n ->
                        WifiNetworkData(
                            ssid = n.ssid,
                            bssid = n.bssid,
                            signalDbm = n.signalDbm,
                            frequencyMhz = n.frequencyMhz
                        )
                    },
                    count = wifiResult.networks.size
                ),
                cellTowers = CellTowerData(
                    towers = cellResult.towers.map { t ->
                        CellTowerEntryData(
                            cellId = t.cellId,
                            lac = t.lac,
                            mcc = t.mcc,
                            mnc = t.mnc,
                            signalDbm = t.signalDbm,
                            networkType = t.networkType
                        )
                    },
                    count = cellResult.towers.size
                ),
                environmental = if (env != null) {
                    EnvironmentalSensorData(
                        pressureHpa = env.pressureHpa,
                        altitudeMeters = env.altitudeMeters,
                        lightLux = env.lightLux,
                        magneticField = if (env.magneticX != null) {
                            MagneticFieldData(
                                x = env.magneticX!!,
                                y = env.magneticY!!,
                                z = env.magneticZ!!,
                                magnitude = env.magneticMagnitude ?: 0f
                            )
                        } else null,
                        tremorDetected = env.tremorDetected
                    )
                } else null
            )

            // Triangulate location confidence from all sensors
            val triangulation = locationTriangulator.triangulate(sensorSnapshot)

            _uiState.value = _uiState.value.copy(
                screenState = CameraScreenState.CAPTURED,
                watermarkedPhotoUri = finalUri,
                signatureJson = signatureJson,
                sensorDataJson = sensorSnapshot.toJson(),
                confidenceScore = triangulation.confidenceScore,
                triangulationFlags = triangulation.flags
            )
        }
    }

    fun onLocationUpdated(lat: Double, lon: Double, accuracy: Float) {
        val status = if (accuracy <= 10f) "GPS Ready (±${accuracy.toInt()}m)"
        else if (accuracy <= 50f) "GPS OK (±${accuracy.toInt()}m)"
        else "Low accuracy (±${accuracy.toInt()}m)"

        _uiState.value = _uiState.value.copy(
            latitude = lat,
            longitude = lon,
            accuracy = accuracy,
            gpsStatus = status
        )
    }

    fun retakePhoto() {
        _uiState.value = _uiState.value.copy(
            screenState = CameraScreenState.PREVIEW,
            originalPhotoUri = null,
            watermarkedPhotoUri = null,
            signatureJson = null,
            sensorDataJson = null,
            error = null,
            uploadSuccess = false
        )
    }

    fun uploadPhoto() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isUploading = true,
                error = null,
                screenState = CameraScreenState.UPLOADING
            )
            // TODO: Implement actual upload via PhotoRepository
            kotlinx.coroutines.delay(1500)
            _uiState.value = _uiState.value.copy(
                isUploading = false,
                uploadSuccess = true
            )
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
