package com.trustcapture.vendor

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import com.trustcapture.vendor.data.remote.UploadScheduler
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class TrustCaptureApp : Application(), Configuration.Provider {

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()

    override fun onCreate() {
        super.onCreate()
        // Initialize SQLCipher native library (required for sqlcipher-android)
        System.loadLibrary("sqlcipher")
        // Schedule periodic background upload sync (every 15 min when network available)
        UploadScheduler.schedulePeriodicSync(this)
    }
}
