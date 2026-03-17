package com.trustcapture.vendor.data.remote

import android.content.Context
import android.util.Log
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

private const val TAG = "UploadWorker"

/**
 * WorkManager worker that processes the photo upload queue in the background.
 * Triggered periodically and on network availability changes.
 * Delegates actual upload logic to UploadManager.
 */
@HiltWorker
class UploadWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted workerParams: WorkerParameters,
    private val uploadManager: UploadManager
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        Log.d(TAG, "UploadWorker started — processing pending uploads")
        return try {
            uploadManager.processQueueBlocking()
            val pending = uploadManager.state.value.pendingCount
            if (pending > 0) {
                Log.d(TAG, "UploadWorker finished with $pending still pending — will retry")
                Result.retry()
            } else {
                Log.d(TAG, "UploadWorker finished — all uploads complete")
                Result.success()
            }
        } catch (e: Exception) {
            Log.e(TAG, "UploadWorker failed", e)
            Result.retry()
        }
    }
}
