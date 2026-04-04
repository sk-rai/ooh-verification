package com.trustcapture.vendor.data.remote

import android.content.Context
import android.util.Log
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

private const val TAG = "UploadWorker"

@HiltWorker
class UploadWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted workerParams: WorkerParameters,
    private val uploadManager: UploadManager
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        return try {
            uploadManager.processQueueBlocking()
            val pending = uploadManager.state.value.pendingCount
            val lastError = uploadManager.state.value.lastError
            if (pending > 0) {
                Result.retry()
            } else {
                Result.success()
            }
        } catch (e: Exception) {
            Log.e(TAG, "UploadWorker exception", e)
            Result.retry()
        }
    }
}
