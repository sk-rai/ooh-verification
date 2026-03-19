package com.trustcapture.vendor.data.local.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import com.trustcapture.vendor.data.local.entity.PhotoEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PhotoDao {

    @Insert
    suspend fun insert(photo: PhotoEntity): Long

    @Query("SELECT * FROM photos WHERE uploadStatus = 'PENDING' OR uploadStatus = 'FAILED' ORDER BY createdAt ASC")
    fun getPendingUploads(): Flow<List<PhotoEntity>>

    @Query("SELECT COUNT(*) FROM photos WHERE uploadStatus = 'PENDING' OR uploadStatus = 'FAILED'")
    fun getPendingCount(): Flow<Int>

    @Query("SELECT * FROM photos WHERE campaignId = :campaignId ORDER BY capturedAt DESC")
    fun getPhotosForCampaign(campaignId: String): Flow<List<PhotoEntity>>

    @Query("SELECT * FROM photos WHERE id = :id")
    suspend fun getById(id: Long): PhotoEntity?

    @Query("UPDATE photos SET uploadStatus = :status WHERE id = :id")
    suspend fun updateStatus(id: Long, status: String)

    @Query("UPDATE photos SET uploadStatus = :status, retryCount = retryCount + 1, lastError = :error WHERE id = :id")
    suspend fun markFailed(id: Long, status: String = "FAILED", error: String?)

    @Query("DELETE FROM photos WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("DELETE FROM photos WHERE uploadStatus = 'UPLOADED'")
    suspend fun deleteUploaded()

    /** Reset photos stuck in UPLOADING back to PENDING (stale from crashed workers) */
    @Query("UPDATE photos SET uploadStatus = 'PENDING' WHERE uploadStatus = 'UPLOADING'")
    suspend fun resetStaleUploading()

    /** Reset retry count for photos that maxed out — gives them another chance after a fix */
    @Query("UPDATE photos SET retryCount = 0, uploadStatus = 'PENDING', lastError = NULL WHERE retryCount >= :maxRetries AND uploadStatus = 'FAILED'")
    suspend fun resetMaxRetriedPhotos(maxRetries: Int)

    /** Delete photos that have been stuck failed for over 24 hours */
    @Query("DELETE FROM photos WHERE uploadStatus = 'FAILED' AND retryCount >= :maxRetries AND createdAt < :cutoffMillis")
    suspend fun purgeAbandonedPhotos(maxRetries: Int, cutoffMillis: Long)

    // GDPR data export (Req 24.3)
    @Query("SELECT * FROM photos WHERE vendorId = :vendorId ORDER BY capturedAt DESC")
    suspend fun getAllForVendor(vendorId: String): List<PhotoEntity>

    // GDPR data deletion (Req 24.4)
    @Query("DELETE FROM photos WHERE vendorId = :vendorId")
    suspend fun deleteAllForVendor(vendorId: String)
}
