package com.trustcapture.vendor

import com.google.gson.Gson
import com.google.gson.JsonParser
import com.google.gson.annotations.SerializedName
import com.trustcapture.vendor.data.remote.api.TrackingPointPayload
import com.trustcapture.vendor.data.remote.api.TrackingSyncRequest
import org.junit.Assert.assertEquals
import org.junit.Test

class TrackingSyncSerializationTest {
    @Test
    fun explicitlyPinsWireNamesForMinification() {
        assertWireName(TrackingSyncRequest::class.java, "points", "points")
        assertWireName(TrackingPointPayload::class.java, "lat", "lat")
        assertWireName(TrackingPointPayload::class.java, "lon", "lon")
        assertWireName(TrackingPointPayload::class.java, "accuracy", "accuracy")
        assertWireName(TrackingPointPayload::class.java, "timestampMs", "timestamp_ms")
        assertWireName(TrackingPointPayload::class.java, "batteryPct", "battery_pct")
    }

    @Test
    fun serializesCanonicalPointFieldsAndOmitsNullBattery() {
        val request = TrackingSyncRequest(
            points = listOf(
                TrackingPointPayload(1.25, 2.5, 3.0f, 1000L, 75),
                TrackingPointPayload(1.5, 2.75, 4.0f, 2000L, null)
            )
        )
        val expected = JsonParser.parseString(
            """
            {"points":[
              {"lat":1.25,"lon":2.5,"accuracy":3.0,"timestamp_ms":1000,"battery_pct":75},
              {"lat":1.5,"lon":2.75,"accuracy":4.0,"timestamp_ms":2000}
            ]}
            """.trimIndent()
        )

        assertEquals(expected, Gson().toJsonTree(request))
    }

    private fun assertWireName(type: Class<*>, fieldName: String, wireName: String) {
        val annotation = type.getDeclaredField(fieldName).getAnnotation(SerializedName::class.java)
        assertEquals(wireName, annotation?.value)
    }
}
