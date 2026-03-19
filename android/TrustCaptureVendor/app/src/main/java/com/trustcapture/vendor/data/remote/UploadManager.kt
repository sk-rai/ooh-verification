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
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
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
    private val processingMutex = Mutex()

    private val _state = MutableStateFlow(UploadQueueState())
    val state: StateFlow<UploadQueueState> = _state.asStateFlow()

    /** Fire-and-forget version for UI calls. */
    fun processQueue() {
        scope.launch { processQueueInternal() }
    }

    /** Suspend version for WorkManager — waits for completion. */
    suspend fun processQueueBlocking() {
        processQueueInternal()
    }

    private suspend fun processQueueInternal() {
        // Mutex ensures only one processing loop runs at a time.
        // Other callers wait instead of bailing out.
        processingMutex.withLock {
            _state.value = _state.value.copy(isProcessing = true, lastError = null)
            try {
                // Reset any photos stuck in UPLOADING (stale from crashed workers)
                photoRepository.resetStaleUploading()
                processAllPending()
            } catch (e: Exception) {
                Log.e(TAG, "processQueueInternal failed", e)
                _state.value = _state.value.copy(lastError = e.message)
            } finally {
                _state.value = _state.value.copy(isProcessing = false)
                cleanupCompleted()
            }
        }
    }

    private suspend fun cleanupCompleted() {
        try { photoRepository.cleanupUploaded() } catch (e: Exception) { Log.w(TAG, "Cleanup failed", e) }
    }

    private suspend fun processAllPending() {
        val pendingPhotos = photoRepository.getPendingUploads().first()
        Log.d(TAG, "processAllPending: ${pendingPhotos.size} photos queued")
        _state.value = _state.value.copy(pendingCount = pendingPhotos.size)

        if (pendingPhotos.isEmpty()) return

        if (!isNetworkAvailable()) {
            Log.w(TAG, "No network — skipping upload cycle")
            _state.value = _state.value.copy(lastError = "No network connection")
            return
        }

        for (photo in pendingPhotos) {
            if (photo.retryCount >= MAX_RETRIES) {
                Log.w(TAG, "Photo ${photo.id} exceeded max retries (${photo.retryCount}), skipping")
                continue
            }
            uploadSinglePhoto(photo)
        }
    }

    private suspend fun uploadSinglePhoto(photo: PhotoEntity) {
        Log.d(TAG, "Uploading photo ${photo.id} (campaign=${photo.campaignCode}, retry=${photo.retryCount})")
        try {
            photoRepository.markUploading(photo.id)

            val photoBytes = photoRepository.decryptForUpload(photo.encryptedPath)
            Log.d(TAG, "Photo ${photo.id} decrypted (${photoBytes.size} bytes)")

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
            val campaignCodeBody = photo.campaignCode.toRequestBody("text/plain".toMediaType())
            val timestampBody = formatTimestamp(photo.capturedAt).toRequestBody("text/plain".toMediaType())

            Log.d(TAG, "Photo ${photo.id} sending to backend...")
            val response = photoApi.uploadPhoto(
                photo = photoPart, sensorData = sensorDataBody, signature = signatureBody,
                campaignCode = campaignCodeBody, captureTimestamp = timestampBody
            )

            if (response.isSuccessful) {
                Log.d(TAG, "Photo ${photo.id} uploaded OK — server id=${response.body()?.photoId}")
                photoRepository.markUploaded(photo.id)
                photoRepository.deleteAfterUpload(photo.id)
                auditRepository.log(
                    eventType = "PHOTO_UPLOADED", vendorId = photo.vendorId,
                    deviceId = "trustcapture_device_key", photoId = photo.id,
                    details = """{"server_photo_id":"${response.body()?.photoId}","verification":"${response.body()?.verificationStatus}","confidence":${response.body()?.verificationConfidence ?: "null"},"flags":${response.body()?.verificationFlags?.let { "[${it.joinToString(",") { f -> "\"$f\"" }}]" } ?: "null"}}""",
                    emulatorMode = photo.emulatorMode
                )
                _state.value = _state.value.copy(pendingCount = (_state.value.pendingCount - 1).coerceAtLeast(0))
            } else {
                val errorMsg = response.errorBody()?.string() ?: "Upload failed (${response.code()})"
                Log.e(TAG, "Photo ${photo.id} upload failed: $errorMsg")
                photoRepository.markFailed(photo.id, errorMsg)
                auditRepository.log(
                    eventType = "UPLOAD_FAILED", vendorId = photo.vendorId,
                    deviceId = "trustcapture_device_key", photoId = photo.id,
                    details = """{"code":${response.code()},"error":"$errorMsg"}""",
                    emulatorMode = photo.emulatorMode
                )
                _state.value = _state.value.copy(lastError = errorMsg)
                delay(BASE_DELAY_MS * (1L shl photo.retryCount.coerceAtMost(4)))
            }
        } catch (e: Exception) {
            val errorMsg = e.localizedMessage ?: "Upload exception"
            Log.e(TAG, "Photo ${photo.id} exception: $errorMsg", e)
            photoRepository.markFailed(photo.id, errorMsg)
            _state.value = _state.value.copy(lastError = errorMsg)
            delay(BASE_DELAY_MS * (1L shl photo.retryCount.coerceAtMost(4)))
        }
    }

    private fun formatTimestamp(epochMillis: Long): String {
        return DateTimeFormatter.ISO_INSTANT.withZone(ZoneOffset.UTC).format(Instant.ofEpochMilli(epochMillis))
    }

    private fun isNetworkAvailable(): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
}
