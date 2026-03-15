package com.trustcapture.vendor.util

import android.annotation.SuppressLint
import android.content.Context
import android.os.Looper
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

data class LocationUpdate(
    val latitude: Double,
    val longitude: Double,
    val accuracy: Float,
    val altitude: Double?
)

@SuppressLint("MissingPermission")
fun locationUpdates(context: Context): Flow<LocationUpdate> = callbackFlow {
    val client: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(context)

    val request = LocationRequest.Builder(
        Priority.PRIORITY_HIGH_ACCURACY, 2000L
    ).setMinUpdateIntervalMillis(1000L).build()

    val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.lastLocation?.let { loc ->
                trySend(
                    LocationUpdate(
                        latitude = loc.latitude,
                        longitude = loc.longitude,
                        accuracy = loc.accuracy,
                        altitude = if (loc.hasAltitude()) loc.altitude else null
                    )
                )
            }
        }
    }

    client.requestLocationUpdates(request, callback, Looper.getMainLooper())

    awaitClose { client.removeLocationUpdates(callback) }
}
