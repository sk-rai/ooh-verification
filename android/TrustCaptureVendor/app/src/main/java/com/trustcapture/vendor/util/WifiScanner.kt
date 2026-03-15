package com.trustcapture.vendor.util

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.wifi.WifiManager
import android.os.Build
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * A single WiFi network seen during a scan.
 */
data class WifiNetwork(
    val ssid: String,
    val bssid: String,
    val signalDbm: Int,
    val frequencyMhz: Int,
    val channelWidth: String? = null
)

/**
 * Result of a WiFi scan — list of nearby networks.
 */
data class WifiScanResult(
    val networks: List<WifiNetwork>,
    val scanTimestamp: Long = System.currentTimeMillis()
)

/**
 * Scans for nearby WiFi networks using WifiManager.
 * Returns up to 10 strongest networks sorted by signal strength.
 *
 * On emulator, WiFi scanning typically returns empty results —
 * this is expected and handled gracefully.
 */
@Singleton
class WifiScanner @Inject constructor() {

    /**
     * Triggers a WiFi scan and emits results.
     * Completes after receiving one scan result.
     */
    fun scan(context: Context): Flow<WifiScanResult> = callbackFlow {
        val wifiManager = context.applicationContext
            .getSystemService(Context.WIFI_SERVICE) as WifiManager

        val receiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context, intent: Intent) {
                val success = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    intent.getBooleanExtra(WifiManager.EXTRA_RESULTS_UPDATED, false)
                } else true

                val results = wifiManager.scanResults
                    .sortedByDescending { it.level }
                    .take(10)
                    .map { sr ->
                        WifiNetwork(
                            ssid = sr.SSID ?: "<hidden>",
                            bssid = sr.BSSID ?: "",
                            signalDbm = sr.level,
                            frequencyMhz = sr.frequency,
                            channelWidth = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                                when (sr.channelWidth) {
                                    0 -> "20MHz"
                                    1 -> "40MHz"
                                    2 -> "80MHz"
                                    3 -> "160MHz"
                                    4 -> "80+80MHz"
                                    else -> null
                                }
                            } else null
                        )
                    }

                trySend(WifiScanResult(networks = results))
                channel.close()
            }
        }

        context.applicationContext.registerReceiver(
            receiver,
            IntentFilter(WifiManager.SCAN_RESULTS_AVAILABLE_ACTION)
        )

        // Trigger scan — may fail silently on some devices/emulators
        @Suppress("DEPRECATION")
        wifiManager.startScan()

        awaitClose {
            try {
                context.applicationContext.unregisterReceiver(receiver)
            } catch (_: Exception) {}
        }
    }

    /**
     * Gets the last known scan results without triggering a new scan.
     * Useful as a fallback if startScan() is throttled.
     */
    fun getLastResults(context: Context): WifiScanResult {
        val wifiManager = context.applicationContext
            .getSystemService(Context.WIFI_SERVICE) as WifiManager

        val results = wifiManager.scanResults
            .sortedByDescending { it.level }
            .take(10)
            .map { sr ->
                WifiNetwork(
                    ssid = sr.SSID ?: "<hidden>",
                    bssid = sr.BSSID ?: "",
                    signalDbm = sr.level,
                    frequencyMhz = sr.frequency
                )
            }

        return WifiScanResult(networks = results)
    }
}
