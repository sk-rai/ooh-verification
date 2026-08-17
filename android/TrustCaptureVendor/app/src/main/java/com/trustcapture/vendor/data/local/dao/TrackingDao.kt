package com.trustcapture.vendor.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import com.trustcapture.vendor.data.local.entity.TrackingPointEntity

@Dao
interface TrackingDao {

    @Insert
    suspend fun insert(point: TrackingPointEntity)

    @Query("SELECT * FROM tracking_points WHERE synced = 0 ORDER BY timestampMs ASC")
    suspend fun getUnsynced(): List<TrackingPointEntity>

    @Query("UPDATE tracking_points SET synced = 1 WHERE id IN (:ids)")
    suspend fun markSynced(ids: List<Long>)

    @Query("DELETE FROM tracking_points WHERE synced = 1 AND timestampMs < :olderThan")
    suspend fun cleanupOld(olderThan: Long)

    @Query("SELECT * FROM tracking_points WHERE timestampMs >= :startOfDay ORDER BY timestampMs ASC")
    suspend fun getTodayPoints(startOfDay: Long): List<TrackingPointEntity>

    @Query("SELECT COUNT(*) FROM tracking_points WHERE synced = 0")
    suspend fun getUnsyncedCount(): Int
}
