package com.trustcapture.vendor.di

import android.content.Context
import androidx.room.Room
import com.trustcapture.vendor.data.local.db.AppDatabase
import com.trustcapture.vendor.data.local.db.CampaignDao
import com.trustcapture.vendor.data.local.db.PhotoDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AppDatabase =
        Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            "trustcapture.db"
        ).fallbackToDestructiveMigration().build()

    @Provides
    fun provideCampaignDao(db: AppDatabase): CampaignDao = db.campaignDao()

    @Provides
    fun providePhotoDao(db: AppDatabase): PhotoDao = db.photoDao()
}
