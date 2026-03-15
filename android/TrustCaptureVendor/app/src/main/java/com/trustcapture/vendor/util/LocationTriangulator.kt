package com.trustcapture.vendor.util

import java.security.MessageDigest
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Confidence assessment result from triangulating all sensor data.
 */
data class TriangulationResult(
    val confidenceScore: Int,           // 0-100
    val locationHash: String,           // SHA-256 hex of combined sensor data
    val sensorCount: Int,               // Number of sensors that contributed data
    val flags: List<String>,            // Discrepancy warnings
    val breakdown: ConfidenceBreakdown  // Per-sensor scores
)

/**
 * Per-sensor confidence contributions.
 * Each score is 0-100 representing that sensor's reliability.
 */
data class ConfidenceBreakdown(
    val gpsScore: Int = 0,
    val wifiScore: Int = 0,
    val cellTowerScore: Int = 0,
    val pressureScore: Int = 0,
    val lightScore: Int = 0,
    val magneticScore: Int = 0,
    val tremorPenalty: Int = 0
)

/**
 * Aggregates all sensor data, calculates a location confidence score,
 * generates a deterministic location hash, and flags discrepancies.
 *
 * The confidence score (0-100) reflects how much sensor data is available
 * and how consistent the readings are. Higher scores mean more sensors
 * agree and more data points are present.
 *
 * Scoring weights:
 *   GPS accuracy:       30 points max
 *   WiFi networks:      20 points max
 *   Cell towers:        15 points max
 *   Barometric pressure: 15 points max
 *   Magnetic field:      10 points max
 *   Ambient light:       10 points max
 *   Tremor penalty:      -10 points if detected
 */
@Singleton
class LocationTriangulator @Inject constructor() {

    companion object {
        // Weight allocation (total = 100)
        private const val GPS_WEIGHT = 30
        private const val WIFI_WEIGHT = 20
        private const val CELL_WEIGHT = 15
        private const val PRESSURE_WEIGHT = 15
        private const val MAGNETIC_WEIGHT = 10
        private const val LIGHT_WEIGHT = 10
        private const val TREMOR_PENALTY = 10
    }

    /**
     * Triangulates location confidence from a sensor data snapshot.
     * Returns a TriangulationResult with score, hash, and flags.
     */
    fun triangulate(snapshot: SensorDataSnapshot): TriangulationResult {
        val flags = mutableListOf<String>()
        var sensorCount = 0

        // --- GPS Score ---
        val gpsScore = scoreGps(snapshot.gps)
        if (snapshot.gps != null) sensorCount++
        if (snapshot.gps == null) flags.add("NO_GPS")
        if (snapshot.gps != null && snapshot.gps.accuracy > 50f) {
            flags.add("LOW_GPS_ACCURACY")
        }

        // --- WiFi Score ---
        val wifiScore = scoreWifi(snapshot.wifi)
        if (snapshot.wifi != null && snapshot.wifi.count > 0) sensorCount++
        if (snapshot.wifi == null || snapshot.wifi.count == 0) flags.add("NO_WIFI")

        // --- Cell Tower Score ---
        val cellScore = scoreCellTowers(snapshot.cellTowers)
        if (snapshot.cellTowers != null && snapshot.cellTowers.count > 0) sensorCount++
        if (snapshot.cellTowers == null || snapshot.cellTowers.count == 0) flags.add("NO_CELL_TOWERS")

        // --- Pressure Score ---
        val pressureScore = scorePressure(snapshot.environmental)
        if (snapshot.environmental?.pressureHpa != null) sensorCount++
        if (snapshot.environmental?.pressureHpa == null) flags.add("NO_BAROMETER")

        // --- Magnetic Score ---
        val magneticScore = scoreMagnetic(snapshot.environmental)
        if (snapshot.environmental?.magneticField != null) sensorCount++

        // --- Light Score ---
        val lightScore = scoreLight(snapshot.environmental)
        if (snapshot.environmental?.lightLux != null) sensorCount++

        // --- Tremor Penalty ---
        val tremorPen = if (snapshot.environmental?.tremorDetected == true) {
            flags.add("TREMOR_DETECTED")
            TREMOR_PENALTY
        } else 0

        // --- Discrepancy Detection ---
        detectDiscrepancies(snapshot, flags)

        // --- Total Score ---
        val rawScore = gpsScore + wifiScore + cellScore + pressureScore +
                magneticScore + lightScore - tremorPen
        val finalScore = rawScore.coerceIn(0, 100)

        // --- Location Hash ---
        val locationHash = generateLocationHash(snapshot)

        val breakdown = ConfidenceBreakdown(
            gpsScore = gpsScore,
            wifiScore = wifiScore,
            cellTowerScore = cellScore,
            pressureScore = pressureScore,
            lightScore = lightScore,
            magneticScore = magneticScore,
            tremorPenalty = tremorPen
        )

        return TriangulationResult(
            confidenceScore = finalScore,
            locationHash = locationHash,
            sensorCount = sensorCount,
            flags = flags,
            breakdown = breakdown
        )
    }

    // --- Scoring Functions ---

    private fun scoreGps(gps: GpsData?): Int {
        if (gps == null) return 0
        // Better accuracy = higher score
        return when {
            gps.accuracy <= 5f -> GPS_WEIGHT          // Excellent
            gps.accuracy <= 10f -> (GPS_WEIGHT * 0.9).toInt()
            gps.accuracy <= 20f -> (GPS_WEIGHT * 0.7).toInt()
            gps.accuracy <= 50f -> (GPS_WEIGHT * 0.5).toInt()
            gps.accuracy <= 100f -> (GPS_WEIGHT * 0.3).toInt()
            else -> (GPS_WEIGHT * 0.1).toInt()         // Very poor
        }
    }

    private fun scoreWifi(wifi: WifiData?): Int {
        if (wifi == null || wifi.count == 0) return 0
        // More networks = higher confidence in location
        return when {
            wifi.count >= 5 -> WIFI_WEIGHT
            wifi.count >= 3 -> (WIFI_WEIGHT * 0.8).toInt()
            wifi.count >= 1 -> (WIFI_WEIGHT * 0.5).toInt()
            else -> 0
        }
    }

    private fun scoreCellTowers(cell: CellTowerData?): Int {
        if (cell == null || cell.count == 0) return 0
        return when {
            cell.count >= 3 -> CELL_WEIGHT
            cell.count >= 2 -> (CELL_WEIGHT * 0.7).toInt()
            cell.count >= 1 -> (CELL_WEIGHT * 0.5).toInt()
            else -> 0
        }
    }

    private fun scorePressure(env: EnvironmentalSensorData?): Int {
        val pressure = env?.pressureHpa ?: return 0
        // Valid sea-level pressure range: 870-1084 hPa
        return if (pressure in 870f..1084f) PRESSURE_WEIGHT
        else (PRESSURE_WEIGHT * 0.3).toInt() // Suspicious reading
    }

    private fun scoreMagnetic(env: EnvironmentalSensorData?): Int {
        val mag = env?.magneticField ?: return 0
        // Earth's magnetic field: ~25-65 µT
        return if (mag.magnitude in 20f..70f) MAGNETIC_WEIGHT
        else (MAGNETIC_WEIGHT * 0.3).toInt() // Possible interference
    }

    private fun scoreLight(env: EnvironmentalSensorData?): Int {
        val lux = env?.lightLux ?: return 0
        // Any reading is useful — just confirms sensor is working
        return if (lux >= 0f) LIGHT_WEIGHT else 0
    }

    // --- Discrepancy Detection ---

    private fun detectDiscrepancies(snapshot: SensorDataSnapshot, flags: MutableList<String>) {
        val env = snapshot.environmental ?: return

        // GPS says high altitude but pressure says sea level
        val gpsAlt = snapshot.gps?.altitude
        val pressureAlt = env.altitudeMeters
        if (gpsAlt != null && pressureAlt != null) {
            val altDiff = kotlin.math.abs(gpsAlt - pressureAlt)
            if (altDiff > 200) {
                flags.add("ALTITUDE_MISMATCH")
            }
        }

        // Magnetic field way outside Earth's range — possible spoofing or interference
        val mag = env.magneticField?.magnitude
        if (mag != null && (mag < 15f || mag > 80f)) {
            flags.add("MAGNETIC_ANOMALY")
        }

        // Very low light but GPS has good accuracy (outdoor?) — could be suspicious
        val lux = env.lightLux
        val gpsAccuracy = snapshot.gps?.accuracy
        if (lux != null && lux < 5f && gpsAccuracy != null && gpsAccuracy < 10f) {
            flags.add("LOW_LIGHT_HIGH_GPS")
        }
    }

    // --- Location Hash ---

    /**
     * Generates a deterministic SHA-256 hash from all sensor data.
     * This hash binds the sensor readings to the photo for tamper detection.
     * Same inputs always produce the same hash.
     */
    fun generateLocationHash(snapshot: SensorDataSnapshot): String {
        val data = buildString {
            // GPS
            snapshot.gps?.let { gps ->
                append("gps:%.7f,%.7f,%.1f|".format(gps.latitude, gps.longitude, gps.accuracy))
                gps.altitude?.let { append("alt:%.1f|".format(it)) }
            }
            // WiFi BSSIDs (sorted for determinism)
            snapshot.wifi?.networks
                ?.map { it.bssid }
                ?.sorted()
                ?.forEach { append("wifi:$it|") }
            // Cell towers (sorted by cell ID for determinism)
            snapshot.cellTowers?.towers
                ?.sortedBy { it.cellId }
                ?.forEach { append("cell:${it.cellId},${it.lac},${it.mcc},${it.mnc}|") }
            // Environmental
            snapshot.environmental?.let { env ->
                env.pressureHpa?.let { append("pressure:%.1f|".format(it)) }
                env.magneticField?.let { append("mag:%.1f|".format(it.magnitude)) }
            }
        }

        val digest = MessageDigest.getInstance("SHA-256")
        return digest.digest(data.toByteArray()).joinToString("") { "%02x".format(it) }
    }
}
