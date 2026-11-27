package com.trustcapture.vendor.di

import android.content.Context
import androidx.room.Room
import com.trustcapture.vendor.data.local.dao.EvidenceDao
import com.trustcapture.vendor.data.local.dao.TrackingDao
import com.trustcapture.vendor.data.local.db.AppDatabase
import com.trustcapture.vendor.data.local.db.AuditDao
import com.trustcapture.vendor.data.local.db.CampaignDao
import com.trustcapture.vendor.data.local.db.INSPECTION_DRAFT_MIGRATION_10_11
import com.trustcapture.vendor.data.local.db.INSPECTION_CAPTURE_MIGRATION_11_12
import com.trustcapture.vendor.data.local.db.INSPECTION_CAPTURE_MIGRATION_12_13
import com.trustcapture.vendor.data.local.db.InspectionDraftDao
import com.trustcapture.vendor.data.local.db.InspectionEvidenceDao
import com.trustcapture.vendor.data.local.db.PhotoDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import net.zetetic.database.sqlcipher.SupportOpenHelperFactory
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AppDatabase {
        val dbName = "trustcapture_v2.db"

        // Delete legacy unencrypted DB if it exists (from pre-SQLCipher builds)
        val legacyDb = context.getDatabasePath("trustcapture.db")
        if (legacyDb.exists()) {
            legacyDb.delete()
            // Also clean up WAL/SHM journal files
            java.io.File(legacyDb.path + "-wal").delete()
            java.io.File(legacyDb.path + "-shm").delete()
        }

        val passphrase = "trustcapture_db_key".toByteArray()
        val factory = SupportOpenHelperFactory(passphrase)

        return Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            dbName
        )
            .openHelperFactory(factory)
            .addMigrations(
                INSPECTION_DRAFT_MIGRATION_10_11,
                INSPECTION_CAPTURE_MIGRATION_11_12,
                INSPECTION_CAPTURE_MIGRATION_12_13
            )
            .build()
    }

    @Provides
    fun provideCampaignDao(db: AppDatabase): CampaignDao = db.campaignDao()

    @Provides
    fun providePhotoDao(db: AppDatabase): PhotoDao = db.photoDao()

    @Provides
    fun provideAuditDao(db: AppDatabase): AuditDao = db.auditDao()

    @Provides
    fun provideEvidenceDao(db: AppDatabase): EvidenceDao = db.evidenceDao()

    @Provides
    fun provideTrackingDao(db: AppDatabase): TrackingDao = db.trackingDao()

    @Provides
    fun provideInspectionDraftDao(db: AppDatabase): InspectionDraftDao = db.inspectionDraftDao()

    @Provides
    fun provideInspectionEvidenceDao(db: AppDatabase): InspectionEvidenceDao = db.inspectionEvidenceDao()
}
