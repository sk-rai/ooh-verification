package com.trustcapture.vendor.util

import com.google.gson.GsonBuilder
import com.google.gson.JsonObject
import com.google.gson.JsonArray
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * Structured JSON serializer for sensor data (Req 26.1-26.6).
 *
 * Produces a deterministic JSON payload with:
 * - ISO 8601 timestamps (UTC)
 * - GPS coordinates at 7-decimal precision
 * - Schema version for backward compatibility
 * - All sensor sources: GPS, WiFi, cell towers, environmental
 */
object SensorDataSerializer {

    private const val SCHEMA_VERSION = "2.1"
    private val isoFormatter = DateTimeFormatter.ISO_INSTANT.withZone(ZoneOffset.UTC)
    private val gson = GsonBuilder().setPrettyPrinting().serializeNulls().create()

    /**
     * Serialize a SensorDataSnapshot to structured JSON.
     * @param snapshot The sensor data captured at photo time
     * @param captureTimestamp Epoch millis of the capture moment
     * @return Formatted JSON string
     */
    fun serialize(snapshot: SensorDataSnapshot, captureTimestamp: Long = System.currentTimeMillis()): String {
        val root = JsonObject()
        root.addProperty("schema_version", SCHEMA_VERSION)
        root.addProperty("capture_timestamp", isoFormatter.format(Instant.ofEpochMilli(captureTimestamp)))

        // GPS — 7 decimal places (Req 26.3)
        snapshot.gps?.let { gps ->
            val gpsObj = JsonObject()
            gpsObj.addProperty("latitude", "%.7f".format(gps.latitude).toDouble())
            gpsObj.addProperty("longitude", "%.7f".format(gps.longitude).toDouble())
            gpsObj.addProperty("accuracy", gps.accuracy)
            gps.altitude?.let { gpsObj.addProperty("altitude", it) }
            root.add("gps", gpsObj)
        }

        // WiFi networks
        snapshot.wifi?.let { wifi ->
            val wifiArr = JsonArray()
            for (n in wifi.networks) {
                val obj = JsonObject()
                obj.addProperty("ssid", n.ssid)
                obj.addProperty("bssid", n.bssid)
                obj.addProperty("signal_dbm", n.signalDbm)
                obj.addProperty("frequency_mhz", n.frequencyMhz)
                wifiArr.add(obj)
            }
            root.add("wifi_networks", wifiArr)
            root.addProperty("wifi_count", wifi.count)
        }

        // Cell towers
        snapshot.cellTowers?.let { ct ->
            val towersArr = JsonArray()
            for (t in ct.towers) {
                val obj = JsonObject()
                obj.addProperty("cell_id", t.cellId)
                obj.addProperty("lac", t.lac)
                obj.addProperty("mcc", t.mcc)
                obj.addProperty("mnc", t.mnc)
                obj.addProperty("signal_dbm", t.signalDbm)
                obj.addProperty("network_type", t.networkType)
                towersArr.add(obj)
            }
            root.add("cell_towers", towersArr)
            root.addProperty("cell_tower_count", ct.count)
        }

        // Environmental sensors
        snapshot.environmental?.let { env ->
            val envObj = JsonObject()
            env.pressureHpa?.let { envObj.addProperty("pressure_hpa", it) }
            env.altitudeMeters?.let { envObj.addProperty("altitude_meters", it) }
            env.lightLux?.let { envObj.addProperty("light_lux", it) }
            env.magneticField?.let { mag ->
                val magObj = JsonObject()
                magObj.addProperty("x", mag.x)
                magObj.addProperty("y", mag.y)
                magObj.addProperty("z", mag.z)
                magObj.addProperty("magnitude", mag.magnitude)
                envObj.add("magnetic_field", magObj)
            }
            env.accelerometer?.let { accel ->
                val accelObj = JsonObject()
                accelObj.addProperty("x", accel.x)
                accelObj.addProperty("y", accel.y)
                accelObj.addProperty("z", accel.z)
                envObj.add("accelerometer", accelObj)
            }
            env.gyroscope?.let { gyro ->
                val gyroObj = JsonObject()
                gyroObj.addProperty("x", gyro.x)
                gyroObj.addProperty("y", gyro.y)
                gyroObj.addProperty("z", gyro.z)
                envObj.add("gyroscope", gyroObj)
            }
            env.orientation?.let { orient ->
                val orientObj = JsonObject()
                orientObj.addProperty("x", orient.x)
                orientObj.addProperty("y", orient.y)
                orientObj.addProperty("z", orient.z)
                envObj.add("orientation", orientObj)
            }
            envObj.addProperty("tremor_detected", env.tremorDetected)
            root.add("environmental", envObj)
        }

        return gson.toJson(root)
    }

    /**
     * Deserialize JSON back to SensorDataSnapshot (Req 26.6 round-trip).
     */
    fun deserialize(json: String): SensorDataSnapshot {
        return gson.fromJson(json, SensorDataSnapshot::class.java)
    }
}
