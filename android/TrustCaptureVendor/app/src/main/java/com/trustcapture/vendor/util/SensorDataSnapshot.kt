package com.trustcapture.vendor.util

import com.google.gson.Gson
import com.google.gson.annotations.SerializedName

/**
 * Complete sensor data snapshot captured at the moment of photo capture.
 * Serialized to JSON for the `sensor_data` field in the upload payload.
 */
data class SensorDataSnapshot(
    @SerializedName("gps") val gps: GpsData? = null,
    @SerializedName("wifi") val wifi: WifiData? = null,
    @SerializedName("cell_towers") val cellTowers: CellTowerData? = null,
    @SerializedName("environmental") val environmental: EnvironmentalSensorData? = null,
    @SerializedName("schema_version") val schemaVersion: String = "1.0"
) {
    fun toJson(): String = Gson().toJson(this)
}

data class GpsData(
    @SerializedName("latitude") val latitude: Double,
    @SerializedName("longitude") val longitude: Double,
    @SerializedName("accuracy") val accuracy: Float,
    @SerializedName("altitude") val altitude: Double?
)

data class WifiData(
    @SerializedName("networks") val networks: List<WifiNetworkData>,
    @SerializedName("count") val count: Int
)

data class WifiNetworkData(
    @SerializedName("ssid") val ssid: String,
    @SerializedName("bssid") val bssid: String,
    @SerializedName("signal_dbm") val signalDbm: Int,
    @SerializedName("frequency_mhz") val frequencyMhz: Int
)

data class EnvironmentalSensorData(
    @SerializedName("pressure_hpa") val pressureHpa: Float? = null,
    @SerializedName("altitude_meters") val altitudeMeters: Float? = null,
    @SerializedName("light_lux") val lightLux: Float? = null,
    @SerializedName("magnetic_field") val magneticField: MagneticFieldData? = null,
    @SerializedName("tremor_detected") val tremorDetected: Boolean = false,
    @SerializedName("tremor_frequency") val tremorFrequency: Float? = null,
    @SerializedName("tremor_is_human") val tremorIsHuman: Boolean? = null,
    @SerializedName("tremor_confidence") val tremorConfidence: Float? = null
)

data class MagneticFieldData(
    @SerializedName("x") val x: Float,
    @SerializedName("y") val y: Float,
    @SerializedName("z") val z: Float,
    @SerializedName("magnitude") val magnitude: Float
)

data class CellTowerData(
    @SerializedName("towers") val towers: List<CellTowerEntryData>,
    @SerializedName("count") val count: Int
)

data class CellTowerEntryData(
    @SerializedName("cell_id") val cellId: Int,
    @SerializedName("lac") val lac: Int,
    @SerializedName("mcc") val mcc: Int,
    @SerializedName("mnc") val mnc: Int,
    @SerializedName("signal_dbm") val signalDbm: Int,
    @SerializedName("network_type") val networkType: String
)
