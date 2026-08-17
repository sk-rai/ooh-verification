package com.trustcapture.vendor.domain.repository

import android.util.Log
import com.trustcapture.vendor.data.local.dao.TrackingDao
import com.trustcapture.vendor.data.local.entity.TrackingPointEntity
import com.trustcapture.vendor.data.remote.api.TrackingApi
import com.trustcapture.vendor.data.remote.api.TrackingPointPayload
import com.trustcapture.vendor.data.remote.api.TrackingSyncRequest
import javax.inject.Inject
import javax.inject.Singleton

private const val TAG = "TrackingRepository"

@Singleton
class TrackingRepository @Inject constructor(
    private val trackingDao: TrackingDao,
    private val trackingApi: TrackingApi
) {

    suspend fun savePoint(
        lat: Double,
        lon: Double,
        accuracy: Float,
        timestampMs: Long,
        batteryPct: Int?
    ) {
        trackingDao.insert(
            TrackingPointEntity(
                latitude = lat,
                longitude = lon,
                accuracy = accuracy,
                timestampMs = timestampMs,
                batteryPct = batteryPct
            )
        )
    }

    /**
     * Sync unsynced tracking points to the backend.
     * Returns true if sync succeeded or there was nothing to sync.
     */
    suspend fun syncToBackend(): Boolean {
        val unsynced = trackingDao.getUnsynced()
        if (unsynced.isEmpty()) return true

        return try {
            val payload = TrackingSyncRequest(
                points = unsynced.map { point ->
                    TrackingPointPayload(
                        lat = point.latitude,
                        lon = point.longitude,
                        accuracy = point.accuracy,
                        timestampMs = point.timestampMs,
                        batteryPct = point.batteryPct
                    )
                }
            )

            val response = trackingApi.syncPoints(payload)
            if (response.isSuccessful) {
                trackingDao.markSynced(unsynced.map { it.id })
                // Cleanup old synced points (older than 7 days)
                val sevenDaysAgo = System.currentTimeMillis() - 7 * 24 * 60 * 60 * 1000L
                trackingDao.cleanupOld(sevenDaysAgo)
                Log.i(TAG, "Synced ${unsynced.size} tracking points")
                true
            } else {
                Log.w(TAG, "Sync failed with status ${response.code()}")
                false
            }
        } catch (e: Exception) {
            Log.w(TAG, "Sync failed: ${e.message}")
            false
        }
    }

    suspend fun getUnsyncedCount(): Int = trackingDao.getUnsyncedCount()
}
