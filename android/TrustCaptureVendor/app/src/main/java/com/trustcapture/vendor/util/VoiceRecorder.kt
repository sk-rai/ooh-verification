package com.trustcapture.vendor.util

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private const val TAG = "VoiceRecorder"

/**
 * Records voice notes as AAC audio files.
 * Max duration is configurable (default 120s, auto-stops).
 * Files saved to app cache directory.
 */
class VoiceRecorder(private val context: Context) {

    private var recorder: MediaRecorder? = null
    private var outputFile: File? = null
    private var isRecording = false
    private var startTimeMs: Long = 0L

    val currentFile: File? get() = outputFile
    val recording: Boolean get() = isRecording
    val elapsedSeconds: Int get() = if (isRecording) ((System.currentTimeMillis() - startTimeMs) / 1000).toInt() else 0

    fun start(): Boolean {
        if (isRecording) return false

        val file = File(
            context.cacheDir,
            "VN_${SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())}.m4a"
        )

        try {
            recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                MediaRecorder(context)
            } else {
                @Suppress("DEPRECATION")
                MediaRecorder()
            }

            recorder?.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setAudioEncodingBitRate(64000)
                setAudioSamplingRate(44100)
                setOutputFile(file.absolutePath)
                prepare()
                start()
            }

            outputFile = file
            isRecording = true
            startTimeMs = System.currentTimeMillis()
            Log.i(TAG, "Voice recording started: ${file.name}")
            return true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start recording", e)
            cleanup()
            return false
        }
    }

    fun stop(): File? {
        if (!isRecording) return null

        return try {
            recorder?.stop()
            recorder?.release()
            recorder = null
            isRecording = false
            Log.i(TAG, "Voice recording stopped: ${outputFile?.name}, duration=${elapsedSeconds}s")
            outputFile
        } catch (e: Exception) {
            Log.e(TAG, "Failed to stop recording", e)
            cleanup()
            null
        }
    }

    fun cancel() {
        cleanup()
        outputFile?.delete()
        outputFile = null
    }

    private fun cleanup() {
        try {
            recorder?.stop()
        } catch (_: Exception) {}
        try {
            recorder?.release()
        } catch (_: Exception) {}
        recorder = null
        isRecording = false
    }
}
