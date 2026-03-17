package com.trustcapture.vendor.data.remote

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import com.trustcapture.vendor.data.local.entity.PhotoEntity
import com.trustcapture.vendor.data.remote.api.PhotoApi
import com.trustcapture.vendor.data.remote.dto.CampaignMetadata
import com.trustcapture.vendor.data.remote.dto.UploadPayloadTransformer
import com.trustcapture.vendor.domain.repository.AuditRepository
import com.trustcapture.vendor.domain.repository.PhotoRepository
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import android.util.Log
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import javax.inject.Inject
import javax.inject.Singleton

private const val TAG = "UploadManager"

data class UploadQueueState(
    val pendingCount: Int = 0,
    val isProcessing: Boolean = false,
    val lastError: String? = null
)

/**
 * Manages the photo upload queue with retry logic and offline support.
 * Picks up encrypted photos from the local DB, decrypts them, and uploads
 * to the backend via multipart POST. Retries failed uploads with exponential backoff.
 */
@Singleton
class UploadManager @Inject constructor(
    private val photoApi: PhotoApi,
    private val photoRepository: PhotoRepository,
    private val auditRepository: AuditRepository,
    @ApplicationContext private val context: Context
) {
    companion object {
        private const val MAX_RETRIES = 5
        private const val BASE_DELAY_MS = 2000L
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _state = MutableStateFlow(UploadQueueState())
    val state: StateFlow<UploadQueueState> = _state.asStateFlow()

    /**
     * Starts processing the upload queue. Call after photo capture
     * or when network becomes available.
     */
    fun processQueue() {
        if (_state.value.isProcessing) return
        scope.launch {
            _state.value = _state.value.copy(isProcessing = true, lastError = null)
            try {
                processAllPending()
            } finally {
                _state.value = _state.value.copy(isProcessing = false)
                // Proactively clean up successfully uploaded records and files
                cleanupCompleted()
            }
        }
    }

    /**
     * Blocking (suspend) version for WorkManager. Processes the queue
     * and returns when done. Does not launch a new coroutine.
     */
    suspend fun processQueueBlocking() {
        if (_state.value.isProcessing) return
        _state.value = _state.value.copy(isProcessing = true, lastError = null)
        try {
            processAllPending()
        } finally {
            _state.value = _state.value.copy(isProcessing = false)
            cleanupCompleted()
        }
    }

    /** Remove uploaded photo records and their encrypted files to free disk space. */
    private suspend fun cleanupCompleted() {
        try {
            photoRepository.cleanupUploaded()
        } catch (e: Exception) {
            Log.w(TAG, "Cleanup of uploaded photos failed", e)
        }
    }

    private suspend fun processAllPending() {
        val pendingPhotos = photoRepository.getPendingUploads().first()

        _state.value = _state.value.copy(pendingCount = pendingPhotos.size)

        for (photo in pendingPhotos) {
            if (!isNetworkAvailable()) {
                _state.value = _state.value.copy(lastError = "No network connection")
                return
            }
            if (photo.retryCount >= MAX_RETRIES) continue

            uploadSinglePhoto(photo)
        }
    }

    private suspend fun uploadSinglePhoto(photo: PhotoEntity) {
        try {
            photoRepository.markUploading(photo.id)

            // Decrypt the photo from encrypted storage
            val photoBytes = photoRepository.decryptForUpload(photo.encryptedPath)

            // Build multipart request
            val photoBody = photoBytes.toRequestBody("image/jpeg".toMediaType())
            val photoPart = MultipartBody.Part.createFormData("photo", "photo.jpg", photoBody)

            val sensorDataBody = UploadPayloadTransformer.transformSensorData(
                androidJson = photo.sensorDataJson,
                confidenceScore = photo.confidenceScore,
                campaignMeta = CampaignMetadata(
                    campaignType = photo.campaignType,
                    safetyTags = photo.safetyTags?.split(",")?.filter { it.isNotBlank() } ?: emptyList(),
                    roomLabel = photo.roomLabel ?: "",
                    photoSequence = photo.photoSequence,
                    hipaaCompliant = photo.hipaaCompliant,
                    emulatorMode = photo.emulatorMode
                )
            ).toRequestBody("text/plain".toMediaType())
            val signatureBody = UploadPayloadTransformer.transformSignature(photo.signatureJson)
                .toRequestBody("text/plain".toMediaType())
            val campaignCodeBody = photo.campaignCode
                .toRequestBody("text/plain".toMediaType())
            val timestampBody = formatTimestamp(photo.capturedAt)
                .toRequestBody("text/plain".toMediaType())

            val response = photoApi.uploadPhoto(
                photo = photoPart,
                sensorData = sensorDataBody,
                signature = signatureBody,
                campaignCode = campaignCodeBody,
                captureTimestamp = timestampBody
            )

            if (response.isSuccessful) {
                photoRepository.markUploaded(photo.id)
                // Delete encrypted file after successful upload
                photoRepository.deleteAfterUpload(photo.id)

                auditRepository.log(
                    eventType = "PHOTO_UPLOADED",
                    vendorId = photo.vendorId,
                    deviceId = "trustcapture_device_key",
                    photoId = photo.id,
                    details = """{"server_photo_id":"${response.body()?.photoId}","verification":"${response.body()?.verificationStatus}","confidence":${response.body()?.verificationConfidence ?: "null"},"flags":${response.body()?.verificationFlags?.let { "[${it.joinToString(",") { f -> "\"$f\"" }}]" } ?: "null"}}""",
                    emulatorMode = photo.emulatorMode
                )

                _state.value = _state.value.copy(
                    pendingCount = (_state.value.pendingCount - 1).coerceAtLeast(0)
                )
            } else {
                val errorMsg = response.errorBody()?.string() ?: "Upload failed (${response.code()})"
                photoRepository.markFailed(photo.id, errorMsg)

                auditRepository.log(
                    eventType = "UPLOAD_FAILED",
                    vendorId = photo.vendorId,
                    deviceId = "trustcapture_device_key",
                    photoId = photo.id,
                    details = """{"code":${response.code()},"error":"$errorMsg"}""",
                    emulatorMode = photo.emulatorMode
                )

                _state.value = _state.value.copy(lastError = errorMsg)

                // Exponential backoff before next retry
                val backoff = BASE_DELAY_MS * (1L shl photo.retryCount.coerceAtMost(4))
                delay(backoff)
            }
        } catch (e: Exception) {
            val errorMsg = e.localizedMessage ?: "Upload exception"
            photoRepository.markFailed(photo.id, errorMsg)
            _state.value = _state.value.copy(lastError = errorMsg)

            val backoff = BASE_DELAY_MS * (1L shl photo.retryCount.coerceAtMost(4))
            delay(backoff)
        }
    }

    private fun formatTimestamp(epochMillis: Long): String {
        return DateTimeFormatter.ISO_INSTANT
            .withZone(ZoneOffset.UTC)
            .format(Instant.ofEpochMilli(epochMillis))
    }

    private fun isNetworkAvailable(): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
}
