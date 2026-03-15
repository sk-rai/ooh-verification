package com.trustcapture.vendor.data.local.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.trustcapture.vendor.data.local.entity.CampaignEntity
import com.trustcapture.vendor.data.local.entity.PendingPhotoEntity

@Database(
    entities = [CampaignEntity::class, PendingPhotoEntity::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun campaignDao(): CampaignDao
    abstract fun photoDao(): PhotoDao
}
