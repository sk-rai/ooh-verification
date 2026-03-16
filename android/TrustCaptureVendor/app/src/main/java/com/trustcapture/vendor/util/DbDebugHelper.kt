package com.trustcapture.vendor.util

import android.util.Log
import com.trustcapture.vendor.data.local.db.AuditDao
import com.trustcapture.vendor.data.local.db.PhotoDao
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Debug helper to dump SQLCipher database contents to logcat.
 * Only use in debug builds. Call from CampaignsViewModel or similar.
 */
@Singleton
class DbDebugHelper @Inject constructor(
    private val photoDao: PhotoDao,
    private val auditDao: AuditDao
) {
    suspend fun dumpToLogcat() {
        Log.d("DB_DEBUG", "=== PHOTOS TABLE ===")
        val photos = photoDao.getPendingUploads().first()
        if (photos.isEmpty()) {
            Log.d("DB_DEBUG", "  (no pending photos)")
        }
        photos.forEach { p ->
            Log.d("DB_DEBUG", "  id=${p.id} campaign=${p.campaignCode} vendor=${p.vendorId}")
            Log.d("DB_DEBUG", "    status=${p.uploadStatus} retries=${p.retryCount}")
            Log.d("DB_DEBUG", "    encrypted=${p.encryptedPath}")
            Log.d("DB_DEBUG", "    lat=${p.latitude} lon=${p.longitude} confidence=${p.confidenceScore}")
            Log.d("DB_DEBUG", "    capturedAt=${p.capturedAt} createdAt=${p.createdAt}")
            Log.d("DB_DEBUG", "    sensorData=${p.sensorDataJson.take(200)}...")
            Log.d("DB_DEBUG", "    signature=${p.signatureJson.take(200)}...")
        }

        Log.d("DB_DEBUG", "=== AUDIT_LOGS TABLE ===")
        val audits = auditDao.getUnsynced().first()
        if (audits.isEmpty()) {
            Log.d("DB_DEBUG", "  (no unsynced audit logs)")
        }
        audits.forEach { a ->
            Log.d("DB_DEBUG", "  id=${a.id} event=${a.eventType} vendor=${a.vendorId}")
            Log.d("DB_DEBUG", "    photoId=${a.photoId} synced=${a.synced} ts=${a.timestamp}")
            Log.d("DB_DEBUG", "    details=${a.details}")
        }
        Log.d("DB_DEBUG", "=== END DB DUMP ===")
    }
}
