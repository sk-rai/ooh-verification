package com.trustcapture.vendor.domain.repository

import com.trustcapture.vendor.data.local.db.AuditDao
import com.trustcapture.vendor.data.local.entity.AuditEntity
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuditRepository @Inject constructor(
    private val auditDao: AuditDao
) {
    suspend fun log(
        eventType: String,
        vendorId: String,
        deviceId: String,
        photoId: Long? = null,
        details: String? = null,
        emulatorMode: Boolean = false
    ): Long {
        return auditDao.insert(
            AuditEntity(
                eventType = eventType,
                vendorId = vendorId,
                deviceId = deviceId,
                photoId = photoId,
                details = details,
                emulatorMode = emulatorMode
            )
        )
    }

    fun getUnsynced(): Flow<List<AuditEntity>> = auditDao.getUnsynced()

    fun getUnsyncedCount(): Flow<Int> = auditDao.getUnsyncedCount()

    suspend fun markSynced(id: Long) = auditDao.markSynced(id)
}
