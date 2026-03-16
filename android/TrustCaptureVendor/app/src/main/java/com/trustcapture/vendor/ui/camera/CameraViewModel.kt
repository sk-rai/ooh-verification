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
import com.trustcapture.vendor.domain.model.CampaignTypeConfig
import com.trustcapture.vendor.data.remote.UploadManager
import com.trustcapture.vendor.domain.repository.AuditRepository
import com.trustcapture.vendor.domain.repository.PhotoRepository
import com.trustcapture.vendor.util.GpsPowerMode
import com.trustcapture.vendor.util.KeystoreManager
import com.trustcapture.vendor.util.LocationHelper
import com.trustcapture.vendor.util.SecurityManager
import android.util.Log
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

private const val TAG = "CameraViewModel"

enum class CameraScreenState {
    PREVIEW, PROCESSING, CAPTURED, UPLOADING
}

data class CameraUiState(
    val campaignId: String = "",
    val campaignCode: String = "",
    val campaignType: String = "",
    val campaignConfig: CampaignTypeConfig = CampaignTypeConfig.fromString(""),
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
    val gpsWarning: String? = null,
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
    val uploadSuccess: Boolean = false,
    // Security
    val isEmulator: Boolean = false,
    val isRooted: Boolean = false,
    val securityFlags: List<String> = emptyList(),
    // Keystore / capture blocking
    val keystoreAvailable: Boolean = true,
    val captureBlocked: Boolean = false,
    val captureBlockedReason: String? = null,
    // Campaign-type-specific fields
    val safetyTags: List<String> = emptyList(),
    val roomLabel: String = "",
    val photoSequenceNumber: Int = 1,
    val hipaaFlagged: Boolean = false
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
    private val photoRepository: PhotoRepository,
    private val auditRepository: AuditRepository,
    private val uploadManager: UploadManager,
    private val securityManager: SecurityManager,
    private val keystoreManager: KeystoreManager,
    @ApplicationContext private val appContext: Context
) : ViewModel() {

    private val _uiState = MutableStateFlow(
        CameraUiState(
            campaignId = savedStateHandle.get<String>("campaignId") ?: "",
            campaignCode = savedStateHandle.get<String>("campaignCode") ?: "",
            campaignType = savedStateHandle.get<String>("campaignType") ?: "",
            campaignConfig = CampaignTypeConfig.fromString(
                savedStateHandle.get<String>("campaignType") ?: ""
            )
        )
    )
    val uiState: StateFlow<CameraUiState> = _uiState.asStateFlow()

    init {
        // Run security assessment
        val assessment = securityManager.assess()
        _uiState.value = _uiState.value.copy(
            isEmulator = assessment.isEmulator,
            isRooted = assessment.isRooted,
            securityFlags = assessment.toAuditFlags()
        )

        // Check Keystore availability — block capture if unavailable
        try {
            keystoreManager.generateKeyPairIfNeeded()
            if (!keystoreManager.hasKeyPair()) {
                Log.e(TAG, "Keystore key pair generation failed silently")
                _uiState.value = _uiState.value.copy(
                    keystoreAvailable = false,
                    captureBlocked = true,
                    captureBlockedReason = "Device security not supported"
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Android Keystore unavailable", e)
            _uiState.value = _uiState.value.copy(
                keystoreAvailable = false,
                captureBlocked = true,
                captureBlockedReason = "Device security not supported"
            )
        }

        // Start collecting environmental sensor data (graceful degradation)
        viewModelScope.launch {
            try {
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
            } catch (e: Exception) {
                Log.w(TAG, "Environmental sensors failed, continuing without them", e)
                _uiState.value = _uiState.value.copy(
                    sensorSummary = "Sensors: unavailable"
                )
            }
        }
        // Trigger a WiFi scan (graceful degradation)
        viewModelScope.launch {
            try {
                wifiScanner.scan(appContext).collect { result ->
                    _uiState.value = _uiState.value.copy(wifiCount = result.networks.size)
                }
            } catch (e: Exception) {
                Log.w(TAG, "WiFi scan failed, continuing without WiFi data", e)
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
        // Switch to high-accuracy GPS during capture processing
        LocationHelper.switchMode(GpsPowerMode.HIGH_ACCURACY)

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

        // Req 17.1: warn when GPS accuracy > 50m
        val warning = if (accuracy > 50f) "GPS accuracy too low - move to open area" else null

        _uiState.value = _uiState.value.copy(
            latitude = lat,
            longitude = lon,
            accuracy = accuracy,
            gpsStatus = status,
            gpsWarning = warning
        )
    }

    fun retakePhoto() {
        // Switch back to balanced power mode for idle preview
        LocationHelper.switchMode(GpsPowerMode.BALANCED)

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
            try {
                val state = _uiState.value
                val vendorId = userPreferences.vendorId.first() ?: "UNKNOWN"
                val photoUri = state.watermarkedPhotoUri ?: return@launch

                // Encrypt and save photo locally
                val photoId = photoRepository.savePhoto(
                    photoUri = photoUri,
                    campaignId = state.campaignId,
                    campaignCode = state.campaignCode,
                    campaignType = state.campaignConfig.type.key,
                    vendorId = vendorId,
                    sensorDataJson = state.sensorDataJson ?: "{}",
                    signatureJson = state.signatureJson ?: "{}",
                    latitude = state.latitude,
                    longitude = state.longitude,
                    confidenceScore = state.confidenceScore,
                    triangulationFlags = state.triangulationFlags,
                    safetyTags = state.safetyTags,
                    roomLabel = state.roomLabel,
                    photoSequence = if (state.campaignConfig.allowMultiPhoto) state.photoSequenceNumber else null,
                    hipaaCompliant = state.campaignConfig.enforceHipaa,
                    emulatorMode = state.isEmulator
                )

                // Log audit event
                val securityJson = securityManager.assess().toJson()
                val config = state.campaignConfig
                val extraMeta = buildString {
                    append("""{"campaign":"${state.campaignCode}","confidence":${state.confidenceScore},"security":$securityJson""")
                    append(""","campaign_type":"${config.type.key}"""")
                    append(""","emulator_mode":${state.isEmulator}""")
                    if (config.enforceHipaa) append(""","hipaa_compliant":true""")
                    if (state.safetyTags.isNotEmpty()) append(""","safety_tags":${state.safetyTags.map { "\"$it\"" }}""")
                    if (state.roomLabel.isNotBlank()) append(""","room_label":"${state.roomLabel}"""")
                    if (config.allowMultiPhoto) append(""","photo_sequence":${state.photoSequenceNumber}""")
                    append("}")
                }
                auditRepository.log(
                    eventType = "PHOTO_CAPTURED",
                    vendorId = vendorId,
                    deviceId = "trustcapture_device_key",
                    photoId = photoId,
                    details = extraMeta,
                    emulatorMode = state.isEmulator
                )

                // Trigger upload queue to push to backend
                uploadManager.processQueue()

                // Switch back to balanced power after upload
                LocationHelper.switchMode(GpsPowerMode.BALANCED)

                _uiState.value = _uiState.value.copy(
                    isUploading = false,
                    uploadSuccess = true
                )
            } catch (e: Exception) {
                Log.e(TAG, "Photo save/upload failed", e)
                _uiState.value = _uiState.value.copy(
                    isUploading = false,
                    error = "Upload failed - photo saved for retry",
                    screenState = CameraScreenState.CAPTURED
                )
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    // --- Campaign-type-specific actions ---

    fun addSafetyTag(tag: String) {
        if (tag.isBlank()) return
        val current = _uiState.value.safetyTags
        if (!current.contains(tag.trim())) {
            _uiState.value = _uiState.value.copy(safetyTags = current + tag.trim())
        }
    }

    fun removeSafetyTag(tag: String) {
        _uiState.value = _uiState.value.copy(
            safetyTags = _uiState.value.safetyTags.filter { it != tag }
        )
    }

    fun setRoomLabel(label: String) {
        _uiState.value = _uiState.value.copy(roomLabel = label)
    }

    /** For insurance multi-photo: increment sequence and reset for next capture */
    fun captureAnother() {
        _uiState.value = _uiState.value.copy(
            screenState = CameraScreenState.PREVIEW,
            photoSequenceNumber = _uiState.value.photoSequenceNumber + 1,
            originalPhotoUri = null,
            watermarkedPhotoUri = null,
            signatureJson = null,
            sensorDataJson = null,
            error = null,
            uploadSuccess = false,
            safetyTags = emptyList(),
            roomLabel = ""
        )
    }
}
