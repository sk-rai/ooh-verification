package com.trustcapture.vendor.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.IBinder
import android.os.Looper
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.trustcapture.vendor.MainActivity
import com.trustcapture.vendor.R
import com.trustcapture.vendor.domain.repository.AppConfigRepository
import com.trustcapture.vendor.domain.repository.TrackingRepository
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import javax.inject.Inject

private const val TAG = "TrackingService"

@AndroidEntryPoint
class TrackingService : Service() {

    @Inject lateinit var appConfigRepository: AppConfigRepository
    @Inject lateinit var trackingRepository: TrackingRepository

    private var fusedClient: FusedLocationProviderClient? = null
    private var locationCallback: LocationCallback? = null
    private var startTime: Long = 0L

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    companion object {
        const val ACTION_START = "com.trustcapture.vendor.ACTION_START_TRACKING"
        const val ACTION_STOP = "com.trustcapture.vendor.ACTION_STOP_TRACKING"
        private const val NOTIFICATION_ID = 2001
        private const val CHANNEL_ID = "tracking_channel"

        fun startService(context: Context) {
            val intent = Intent(context, TrackingService::class.java).apply {
                action = ACTION_START
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stopService(context: Context) {
            val intent = Intent(context, TrackingService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startTracking()
            ACTION_STOP -> stopTracking()
        }
        return START_STICKY
    }

    @Suppress("MissingPermission")
    private fun startTracking() {
        val config = appConfigRepository.config.value.trackingConfig
        if (!config.enabled) {
            Log.w(TAG, "Tracking not enabled in config, stopping")
            stopSelf()
            return
        }

        startTime = System.currentTimeMillis()
        Log.i(TAG, "Starting GPS tracking: interval=${config.intervalMinutes}min, maxDuration=${config.maxDurationHours}h")

        // Create notification and start foreground
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, createNotification())

        // Set up location requests
        val intervalMs = config.intervalMinutes * 60 * 1000L
        val request = LocationRequest.Builder(Priority.PRIORITY_BALANCED_POWER_ACCURACY, intervalMs)
            .setMinUpdateIntervalMillis(intervalMs / 2)
            .build()

        locationCallback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                result.lastLocation?.let { location ->
                    if (location.accuracy <= config.minAccuracyMeters) {
                        val batteryPct = if (config.collectBatteryLevel) getBatteryLevel() else null
                        serviceScope.launch {
                            trackingRepository.savePoint(
                                lat = location.latitude,
                                lon = location.longitude,
                                accuracy = location.accuracy,
                                timestampMs = System.currentTimeMillis(),
                                batteryPct = batteryPct
                            )
                        }
                        Log.d(TAG, "Saved tracking point: ${location.latitude}, ${location.longitude} (accuracy: ${location.accuracy}m)")
                    } else {
                        Log.d(TAG, "Skipped point: accuracy ${location.accuracy}m > ${config.minAccuracyMeters}m threshold")
                    }

                    // Check max duration
                    val elapsedHours = (System.currentTimeMillis() - startTime) / (1000.0 * 60 * 60)
                    if (elapsedHours >= config.maxDurationHours) {
                        Log.i(TAG, "Max duration ${config.maxDurationHours}h reached, stopping tracking")
                        stopTracking()
                    }
                }
            }
        }

        fusedClient = LocationServices.getFusedLocationProviderClient(this)
        fusedClient?.requestLocationUpdates(request, locationCallback!!, Looper.getMainLooper())
    }

    private fun stopTracking() {
        Log.i(TAG, "Stopping GPS tracking")
        locationCallback?.let { callback ->
            fusedClient?.removeLocationUpdates(callback)
        }
        locationCallback = null
        fusedClient = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        super.onDestroy()
        locationCallback?.let { callback ->
            fusedClient?.removeLocationUpdates(callback)
        }
        serviceScope.cancel()
    }

    private fun getBatteryLevel(): Int {
        val batteryIntent = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = batteryIntent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = batteryIntent?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        return if (level >= 0 && scale > 0) {
            (level * 100) / scale
        } else {
            -1
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Location Tracking",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows when background location tracking is active"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("TrustCapture")
            .setContentText("Location tracking active")
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()
    }
}
