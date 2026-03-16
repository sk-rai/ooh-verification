package com.trustcapture.vendor.data.local.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.trustcapture.vendor.data.local.entity.AuditEntity
import com.trustcapture.vendor.data.local.entity.CampaignEntity
import com.trustcapture.vendor.data.local.entity.PhotoEntity

@Database(
    entities = [CampaignEntity::class, PhotoEntity::class, AuditEntity::class],
    version = 6,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun campaignDao(): CampaignDao
    abstract fun photoDao(): PhotoDao
    abstract fun auditDao(): AuditDao
}
