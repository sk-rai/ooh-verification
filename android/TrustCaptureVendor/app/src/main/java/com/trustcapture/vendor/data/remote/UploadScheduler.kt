package com.trustcapture.vendor.data.remote

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/**
 * Schedules background upload work via WorkManager.
 *
 * Two strategies:
 * 1. Periodic: runs every 15 min when network is available (catches any stuck uploads)
 * 2. One-shot: triggered immediately after a photo capture to push ASAP
 */
object UploadScheduler {

    private const val PERIODIC_WORK_NAME = "trustcapture_periodic_upload"
    private const val ONESHOT_WORK_NAME = "trustcapture_immediate_upload"

    private val networkConstraints = Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .build()

    /**
     * Enqueue a periodic upload job. Call once at app startup.
     * Uses KEEP policy so it doesn't restart if already scheduled.
     * [intervalMinutes] defaults to 15 but can be set from backend config.
     */
    fun schedulePeriodicSync(context: Context, intervalMinutes: Long = 15L) {
        val request = PeriodicWorkRequestBuilder<UploadWorker>(
            intervalMinutes, TimeUnit.MINUTES
        )
            .setConstraints(networkConstraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()

        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            PERIODIC_WORK_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,  // UPDATE instead of KEEP so interval changes take effect
            request
        )
    }

    /**
     * Trigger an immediate one-shot upload. Call after photo capture.
     * Uses REPLACE policy so a new capture always triggers a fresh attempt.
     */
    fun triggerImmediateUpload(context: Context) {
        val request = OneTimeWorkRequestBuilder<UploadWorker>()
            .setConstraints(networkConstraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
            .build()

        WorkManager.getInstance(context).enqueueUniqueWork(
            ONESHOT_WORK_NAME,
            ExistingWorkPolicy.REPLACE,
            request
        )
    }
}
