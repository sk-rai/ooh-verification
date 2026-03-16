package com.trustcapture.vendor.di

import android.content.Context
import androidx.room.Room
import com.trustcapture.vendor.data.local.db.AppDatabase
import com.trustcapture.vendor.data.local.db.AuditDao
import com.trustcapture.vendor.data.local.db.CampaignDao
import com.trustcapture.vendor.data.local.db.PhotoDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import net.sqlcipher.database.SupportFactory
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

        val passphrase = net.sqlcipher.database.SQLiteDatabase.getBytes("trustcapture_db_key".toCharArray())
        val factory = SupportFactory(passphrase)

        return Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            dbName
        )
            .openHelperFactory(factory)
            .fallbackToDestructiveMigration()
            .build()
    }

    @Provides
    fun provideCampaignDao(db: AppDatabase): CampaignDao = db.campaignDao()

    @Provides
    fun providePhotoDao(db: AppDatabase): PhotoDao = db.photoDao()

    @Provides
    fun provideAuditDao(db: AppDatabase): AuditDao = db.auditDao()
}
