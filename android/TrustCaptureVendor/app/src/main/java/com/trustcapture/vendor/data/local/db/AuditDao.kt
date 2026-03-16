package com.trustcapture.vendor.data.local.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import com.trustcapture.vendor.data.local.entity.AuditEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface AuditDao {

    @Insert
    suspend fun insert(audit: AuditEntity): Long

    @Query("SELECT * FROM audit_logs WHERE synced = 0 ORDER BY timestamp ASC")
    fun getUnsynced(): Flow<List<AuditEntity>>

    @Query("UPDATE audit_logs SET synced = 1 WHERE id = :id")
    suspend fun markSynced(id: Long)

    @Query("SELECT COUNT(*) FROM audit_logs WHERE synced = 0")
    fun getUnsyncedCount(): Flow<Int>

    // GDPR data export (Req 24.3)
    @Query("SELECT * FROM audit_logs WHERE vendorId = :vendorId ORDER BY timestamp DESC")
    suspend fun getAllForVendor(vendorId: String): List<AuditEntity>

    // GDPR data deletion (Req 24.4)
    @Query("DELETE FROM audit_logs WHERE vendorId = :vendorId")
    suspend fun deleteAllForVendor(vendorId: String)
}
