package com.trustcapture.vendor.data.local.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import com.trustcapture.vendor.data.local.entity.PendingPhotoEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface PhotoDao {

    @Query("SELECT * FROM pending_photos WHERE status = 'pending' ORDER BY id ASC")
    fun getPendingPhotos(): Flow<List<PendingPhotoEntity>>

    @Query("SELECT COUNT(*) FROM pending_photos WHERE status = 'pending'")
    fun getPendingCount(): Flow<Int>

    @Insert
    suspend fun insert(photo: PendingPhotoEntity): Long

    @Query("UPDATE pending_photos SET status = :status WHERE id = :id")
    suspend fun updateStatus(id: Long, status: String)

    @Query("DELETE FROM pending_photos WHERE status = 'uploaded'")
    suspend fun deleteUploaded()
}
