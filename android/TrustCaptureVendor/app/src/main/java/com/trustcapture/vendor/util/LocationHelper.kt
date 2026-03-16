package com.trustcapture.vendor.util

import android.annotation.SuppressLint
import android.content.Context
import android.location.LocationManager
import android.os.Looper
import android.util.Log
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

private const val TAG = "LocationHelper"

data class LocationUpdate(
    val latitude: Double,
    val longitude: Double,
    val accuracy: Float,
    val altitude: Double?
)

/**
 * GPS power mode for adaptive location polling.
 * HIGH_ACCURACY: 5s interval, used during active capture session.
 * BALANCED: 15s interval, used when camera screen is idle/reviewing.
 */
enum class GpsPowerMode {
    HIGH_ACCURACY,
    BALANCED
}

/**
 * Adaptive GPS power management with:
 * - Switchable power modes (high accuracy vs balanced)
 * - 30-second location cache (reuse if accuracy ≤ 10m)
 * - GPS timeout with network fallback after 30s
 * - Resource release within 5s after flow cancellation
 */
object LocationHelper {

    private var fusedClient: FusedLocationProviderClient? = null
    private var activeCallback: LocationCallback? = null
    private var currentMode: GpsPowerMode = GpsPowerMode.BALANCED

    // Location cache: reuse if fresh enough and accurate
    private var cachedLocation: LocationUpdate? = null
    private var cacheTimestamp: Long = 0L
    private const val CACHE_TTL_MS = 30_000L      // 30 seconds
    private const val CACHE_ACCURACY_M = 10f       // reuse if ≤ 10m accuracy

    /**
     * Returns cached location if still valid (within 30s and ≤ 10m accuracy).
     */
    fun getCachedLocation(): LocationUpdate? {
        val cached = cachedLocation ?: return null
        val age = System.currentTimeMillis() - cacheTimestamp
        return if (age <= CACHE_TTL_MS && cached.accuracy <= CACHE_ACCURACY_M) cached else null
    }

    private fun buildRequest(mode: GpsPowerMode): LocationRequest {
        return when (mode) {
            GpsPowerMode.HIGH_ACCURACY -> LocationRequest.Builder(
                Priority.PRIORITY_HIGH_ACCURACY, 5_000L
            ).setMinUpdateIntervalMillis(2_000L)
                .setMaxUpdateDelayMillis(8_000L)
                .setWaitForAccurateLocation(true)
                .build()

            GpsPowerMode.BALANCED -> LocationRequest.Builder(
                Priority.PRIORITY_BALANCED_POWER_ACCURACY, 15_000L
            ).setMinUpdateIntervalMillis(10_000L)
                .setMaxUpdateDelayMillis(20_000L)
                .build()
        }
    }

    /**
     * Emits location updates as a callbackFlow.
     * Starts in the given [initialMode] (default BALANCED).
     * Call [switchMode] to change power mode without restarting the flow.
     */
    @SuppressLint("MissingPermission")
    fun locationUpdates(
        context: Context,
        initialMode: GpsPowerMode = GpsPowerMode.BALANCED
    ): Flow<LocationUpdate> = callbackFlow {
        currentMode = initialMode
        fusedClient = LocationServices.getFusedLocationProviderClient(context)
        val client = fusedClient!!

        // Emit cached location immediately if available
        getCachedLocation()?.let {
            trySend(it)
            Log.d(TAG, "Emitted cached location: ${it.latitude}, ${it.longitude}")
        }

        // Also try last known location from fused provider
        try {
            client.lastLocation.addOnSuccessListener { loc ->
                if (loc != null) {
                    val update = LocationUpdate(
                        latitude = loc.latitude,
                        longitude = loc.longitude,
                        accuracy = loc.accuracy,
                        altitude = if (loc.hasAltitude()) loc.altitude else null
                    )
                    updateCache(update)
                    trySend(update)
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to get last location", e)
        }

        val callback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                result.lastLocation?.let { loc ->
                    val update = LocationUpdate(
                        latitude = loc.latitude,
                        longitude = loc.longitude,
                        accuracy = loc.accuracy,
                        altitude = if (loc.hasAltitude()) loc.altitude else null
                    )
                    updateCache(update)
                    trySend(update)
                    Log.d(TAG, "[${currentMode.name}] ${loc.latitude}, ${loc.longitude} ±${loc.accuracy}m")
                }
            }
        }
        activeCallback = callback

        client.requestLocationUpdates(buildRequest(currentMode), callback, Looper.getMainLooper())
        Log.i(TAG, "Started location updates in ${currentMode.name} mode")

        // GPS timeout: if no fix in 30s, try network fallback
        val timeoutHandler = android.os.Handler(Looper.getMainLooper())
        var gotFix = false
        val timeoutRunnable = Runnable {
            if (!gotFix) {
                Log.w(TAG, "GPS timeout after 30s, trying network fallback")
                tryNetworkFallback(context)?.let { trySend(it) }
            }
        }
        timeoutHandler.postDelayed(timeoutRunnable, 30_000L)

        // Track first fix to cancel timeout
        val fixTracker = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                if (!gotFix) {
                    gotFix = true
                    timeoutHandler.removeCallbacks(timeoutRunnable)
                    // Once we have a fix, remove this tracker to save battery
                    client.removeLocationUpdates(this)
                }
            }
        }
        client.requestLocationUpdates(
            buildRequest(GpsPowerMode.HIGH_ACCURACY),
            fixTracker,
            Looper.getMainLooper()
        )

        awaitClose {
            Log.i(TAG, "Releasing location resources")
            client.removeLocationUpdates(callback)
            client.removeLocationUpdates(fixTracker)
            timeoutHandler.removeCallbacks(timeoutRunnable)
            activeCallback = null
            fusedClient = null
        }
    }

    /**
     * Switch GPS power mode without restarting the flow.
     * Call when transitioning between idle and active capture.
     */
    @SuppressLint("MissingPermission")
    fun switchMode(newMode: GpsPowerMode) {
        if (newMode == currentMode) return
        val client = fusedClient ?: return
        val callback = activeCallback ?: return

        currentMode = newMode
        client.removeLocationUpdates(callback)
        client.requestLocationUpdates(buildRequest(newMode), callback, Looper.getMainLooper())
        Log.i(TAG, "Switched GPS to ${newMode.name} mode")
    }

    private fun updateCache(update: LocationUpdate) {
        cachedLocation = update
        cacheTimestamp = System.currentTimeMillis()
    }

    @SuppressLint("MissingPermission")
    private fun tryNetworkFallback(context: Context): LocationUpdate? {
        return try {
            val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
            val loc = lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            loc?.let {
                val update = LocationUpdate(
                    latitude = it.latitude,
                    longitude = it.longitude,
                    accuracy = it.accuracy,
                    altitude = if (it.hasAltitude()) it.altitude else null
                )
                updateCache(update)
                Log.d(TAG, "Network fallback: ${it.latitude}, ${it.longitude}")
                update
            }
        } catch (e: Exception) {
            Log.w(TAG, "Network fallback failed", e)
            null
        }
    }
}
