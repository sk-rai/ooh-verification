package com.trustcapture.vendor.data.remote.dto

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser

/**
 * Transforms the Android sensor data and signature JSON formats
 * to match the backend's expected schema.
 *
 * Android sensor_data format:
 *   { gps: {latitude, longitude, accuracy, altitude},
 *     wifi: { networks: [{ssid, bssid, signal_dbm, frequency_mhz}], count },
 *     cell_towers: { towers: [{cell_id, lac, mcc, mnc, signal_dbm, network_type}], count },
 *     environmental: { pressure_hpa, altitude_meters, light_lux, magnetic_field: {x,y,z,magnitude}, tremor_detected } }
 *
 * Backend sensor_data format:
 *   { gps: {latitude, longitude, accuracy, altitude},
 *     wifi_networks: [{ssid, bssid, signal_strength, frequency}],
 *     cell_towers: [{cell_id, lac, mcc, mnc, signal_strength, network_type}],
 *     environmental: { barometer_pressure, barometer_altitude, ambient_light_lux,
 *                      magnetic_field_x, magnetic_field_y, magnetic_field_z, magnetic_field_magnitude,
 *                      hand_tremor_is_human },
 *     schema_version: "2.0" }
 */
/**
 * Optional campaign-type metadata to include in the upload payload.
 */
data class CampaignMetadata(
    val campaignType: String = "",
    val safetyTags: List<String> = emptyList(),
    val roomLabel: String = "",
    val photoSequence: Int? = null,
    val hipaaCompliant: Boolean = false,
    val emulatorMode: Boolean = false
)

object UploadPayloadTransformer {

    private val gson = Gson()

    fun transformSensorData(
        androidJson: String,
        confidenceScore: Int? = null,
        campaignMeta: CampaignMetadata? = null
    ): String {
        val src = JsonParser.parseString(androidJson).asJsonObject
        val out = JsonObject()

        // GPS — same structure, just pass through
        src.getAsJsonObject("gps")?.let { out.add("gps", it) }

        // WiFi: android "wifi.networks" → backend "wifi_networks"
        src.getAsJsonObject("wifi")?.getAsJsonArray("networks")?.let { networks ->
            val transformed = com.google.gson.JsonArray()
            for (n in networks) {
                val net = n.asJsonObject
                val t = JsonObject()
                t.addProperty("ssid", net.get("ssid")?.asString ?: "")
                t.addProperty("bssid", net.get("bssid")?.asString ?: "")
                t.addProperty("signal_strength", net.get("signal_dbm")?.asInt ?: 0)
                t.addProperty("frequency", net.get("frequency_mhz")?.asInt ?: 0)
                transformed.add(t)
            }
            out.add("wifi_networks", transformed)
        }

        // Cell towers: android "cell_towers.towers" → backend "cell_towers" (flat array)
        src.getAsJsonObject("cell_towers")?.getAsJsonArray("towers")?.let { towers ->
            val transformed = com.google.gson.JsonArray()
            for (t in towers) {
                val tower = t.asJsonObject
                val ct = JsonObject()
                ct.addProperty("cell_id", tower.get("cell_id")?.asInt ?: 0)
                ct.addProperty("lac", tower.get("lac")?.asInt ?: 0)
                ct.addProperty("mcc", tower.get("mcc")?.asInt ?: 0)
                ct.addProperty("mnc", tower.get("mnc")?.asInt ?: 0)
                ct.addProperty("signal_strength", tower.get("signal_dbm")?.asInt ?: 0)
                ct.addProperty("network_type", tower.get("network_type")?.asString ?: "")
                transformed.add(ct)
            }
            out.add("cell_towers", transformed)
        }

        // Environmental: flatten nested structure
        src.getAsJsonObject("environmental")?.let { env ->
            val e = JsonObject()
            env.get("pressure_hpa")?.let { e.addProperty("barometer_pressure", it.asFloat) }
            env.get("altitude_meters")?.let { e.addProperty("barometer_altitude", it.asFloat) }
            env.get("light_lux")?.let { e.addProperty("ambient_light_lux", it.asFloat) }
            env.getAsJsonObject("magnetic_field")?.let { mag ->
                mag.get("x")?.let { e.addProperty("magnetic_field_x", it.asFloat) }
                mag.get("y")?.let { e.addProperty("magnetic_field_y", it.asFloat) }
                mag.get("z")?.let { e.addProperty("magnetic_field_z", it.asFloat) }
                mag.get("magnitude")?.let { e.addProperty("magnetic_field_magnitude", it.asFloat) }
            }
            env.get("tremor_detected")?.let { e.addProperty("hand_tremor_is_human", it.asBoolean) }
            env.get("tremor_frequency")?.let { e.addProperty("hand_tremor_frequency", it.asFloat) }
            env.get("tremor_is_human")?.let { e.addProperty("hand_tremor_is_human", it.asBoolean) }
            env.get("tremor_confidence")?.let { e.addProperty("hand_tremor_confidence", it.asFloat) }
            out.add("environmental", e)
        }

        out.addProperty("schema_version", "2.0")

        // Normalize confidence_score from Android 0-100 int to backend 0-1 float
        confidenceScore?.let { out.addProperty("confidence_score", it / 100.0) }

        // Campaign-type metadata
        campaignMeta?.let { meta ->
            if (meta.campaignType.isNotBlank()) {
                out.addProperty("campaign_type", meta.campaignType)
            }
            if (meta.safetyTags.isNotEmpty()) {
                val tags = com.google.gson.JsonArray()
                meta.safetyTags.forEach { tags.add(it) }
                out.add("safety_tags", tags)
            }
            if (meta.roomLabel.isNotBlank()) {
                out.addProperty("room_label", meta.roomLabel)
            }
            meta.photoSequence?.let { out.addProperty("photo_sequence", it) }
            if (meta.hipaaCompliant) {
                out.addProperty("hipaa_compliant", true)
            }
            if (meta.emulatorMode) {
                out.addProperty("emulator_mode", true)
            }
        }

        return gson.toJson(out)
    }

    /**
     * Transforms the signature JSON to match backend expectations.
     * Main change: algorithm "ECDSA-SHA256" → "ECDSA-P256"
     */
    fun transformSignature(androidJson: String): String {
        val src = JsonParser.parseString(androidJson).asJsonObject
        // Backend validates algorithm is "RSA-2048" or "ECDSA-P256"
        if (src.get("algorithm")?.asString == "ECDSA-SHA256") {
            src.addProperty("algorithm", "ECDSA-P256")
        }
        return gson.toJson(src)
    }
}
