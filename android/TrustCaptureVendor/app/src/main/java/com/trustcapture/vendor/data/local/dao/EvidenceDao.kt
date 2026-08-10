package com.trustcapture.vendor.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import com.trustcapture.vendor.data.local.entity.EvidenceEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface EvidenceDao {
    @Query("SELECT * FROM evidence_queue WHERE status IN ('pending', 'failed') ORDER BY createdAt ASC")
    suspend fun getPendingEvidence(): List<EvidenceEntity>

    @Query("SELECT COUNT(*) FROM evidence_queue WHERE status IN ('pending', 'uploading', 'failed')")
    fun getPendingCount(): Flow<Int>

    @Insert
    suspend fun insert(entity: EvidenceEntity): Long

    @Query("UPDATE evidence_queue SET status = 'uploading' WHERE id = :id")
    suspend fun markUploading(id: Long)

    @Query("UPDATE evidence_queue SET status = 'uploaded' WHERE id = :id")
    suspend fun markUploaded(id: Long)

    @Query("UPDATE evidence_queue SET status = 'failed', retryCount = retryCount + 1, errorMessage = :error WHERE id = :id")
    suspend fun markFailed(id: Long, error: String)

    @Query("DELETE FROM evidence_queue WHERE status = 'uploaded' AND createdAt < :olderThan")
    suspend fun cleanupUploaded(olderThan: Long = System.currentTimeMillis() - 24 * 60 * 60 * 1000)

    @Query("SELECT * FROM evidence_queue WHERE status = 'uploading' AND createdAt < :olderThan")
    suspend fun getStaleUploading(olderThan: Long = System.currentTimeMillis() - 5 * 60 * 1000): List<EvidenceEntity>

    @Query("UPDATE evidence_queue SET status = 'pending' WHERE id = :id")
    suspend fun resetToPending(id: Long)
}
