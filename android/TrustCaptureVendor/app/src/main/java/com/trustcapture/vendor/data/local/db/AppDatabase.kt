package com.trustcapture.vendor.data.local.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.trustcapture.vendor.data.local.dao.EvidenceDao
import com.trustcapture.vendor.data.local.dao.TrackingDao
import com.trustcapture.vendor.data.local.entity.AuditEntity
import com.trustcapture.vendor.data.local.entity.CampaignEntity
import com.trustcapture.vendor.data.local.entity.CampaignLocationEntity
import com.trustcapture.vendor.data.local.entity.EvidenceEntity
import com.trustcapture.vendor.data.local.entity.PhotoEntity
import com.trustcapture.vendor.data.local.entity.TrackingPointEntity

@Database(
    entities = [CampaignEntity::class, CampaignLocationEntity::class, PhotoEntity::class, AuditEntity::class, EvidenceEntity::class, TrackingPointEntity::class],
    version = 10,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun campaignDao(): CampaignDao
    abstract fun photoDao(): PhotoDao
    abstract fun auditDao(): AuditDao
    abstract fun evidenceDao(): EvidenceDao
    abstract fun trackingDao(): TrackingDao
}
