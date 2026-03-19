package com.trustcapture.vendor.domain.repository

import android.content.Context
import android.net.Uri
import com.trustcapture.vendor.data.local.db.PhotoDao
import com.trustcapture.vendor.data.local.entity.PhotoEntity
import com.trustcapture.vendor.data.local.entity.UploadStatus
import com.trustcapture.vendor.util.EncryptionManager
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages local photo storage with encryption.
 * Photos are encrypted at rest and queued for upload.
 */
@Singleton
class PhotoRepository @Inject constructor(
    private val photoDao: PhotoDao,
    private val encryptionManager: EncryptionManager,
    @ApplicationContext private val context: Context
) {
    /**
     * Encrypts a captured photo and saves it to the local database.
     * Returns the inserted photo ID.
     */
    suspend fun savePhoto(
        photoUri: Uri,
        campaignId: String,
        campaignCode: String,
        campaignType: String = "",
        vendorId: String,
        sensorDataJson: String,
        signatureJson: String,
        latitude: Double?,
        longitude: Double?,
        confidenceScore: Int?,
        triangulationFlags: List<String>,
        safetyTags: List<String> = emptyList(),
        roomLabel: String = "",
        photoSequence: Int? = null,
        hipaaCompliant: Boolean = false,
        emulatorMode: Boolean = false
    ): Long = withContext(Dispatchers.IO) {
        // Copy URI content to a temp file, then encrypt
        val tempFile = File(context.cacheDir, "photo_${System.currentTimeMillis()}.jpg")
        context.contentResolver.openInputStream(photoUri)?.use { input ->
            tempFile.outputStream().use { output -> input.copyTo(output) }
        }

        val encryptedPath = encryptionManager.encryptPhoto(tempFile)
        tempFile.delete() // remove unencrypted temp copy

        val entity = PhotoEntity(
            campaignId = campaignId,
            campaignCode = campaignCode,
            campaignType = campaignType,
            vendorId = vendorId,
            originalUri = photoUri.toString(),
            encryptedPath = encryptedPath,
            sensorDataJson = sensorDataJson,
            signatureJson = signatureJson,
            latitude = latitude,
            longitude = longitude,
            confidenceScore = confidenceScore,
            triangulationFlags = triangulationFlags.joinToString(","),
            safetyTags = safetyTags.takeIf { it.isNotEmpty() }?.joinToString(","),
            roomLabel = roomLabel.takeIf { it.isNotBlank() },
            photoSequence = photoSequence,
            hipaaCompliant = hipaaCompliant,
            emulatorMode = emulatorMode,
            capturedAt = System.currentTimeMillis()
        )
        photoDao.insert(entity)
    }

    fun getPendingUploads(): Flow<List<PhotoEntity>> = photoDao.getPendingUploads()

    fun getPendingCount(): Flow<Int> = photoDao.getPendingCount()

    fun getPhotosForCampaign(campaignId: String): Flow<List<PhotoEntity>> =
        photoDao.getPhotosForCampaign(campaignId)

    suspend fun getById(id: Long): PhotoEntity? = photoDao.getById(id)

    /**
     * Decrypts a photo for upload. Returns raw JPEG bytes.
     */
    suspend fun decryptForUpload(encryptedPath: String): ByteArray = withContext(Dispatchers.IO) {
        encryptionManager.decryptPhoto(encryptedPath)
    }

    suspend fun markUploading(id: Long) {
        photoDao.updateStatus(id, UploadStatus.UPLOADING.name)
    }

    suspend fun markUploaded(id: Long) {
        photoDao.updateStatus(id, UploadStatus.UPLOADED.name)
    }

    suspend fun markFailed(id: Long, error: String?) {
        photoDao.markFailed(id = id, error = error)
    }

    /**
     * Deletes the encrypted file and database record after successful upload.
     */
    suspend fun deleteAfterUpload(id: Long) = withContext(Dispatchers.IO) {
        val photo = photoDao.getById(id)
        photo?.let { encryptionManager.deleteEncryptedFile(it.encryptedPath) }
        photoDao.deleteById(id)
    }

    suspend fun cleanupUploaded() = withContext(Dispatchers.IO) {
        photoDao.deleteUploaded()
    }

    /** Reset photos stuck in UPLOADING back to PENDING */
    suspend fun resetStaleUploading() = withContext(Dispatchers.IO) {
        photoDao.resetStaleUploading()
    }
}
