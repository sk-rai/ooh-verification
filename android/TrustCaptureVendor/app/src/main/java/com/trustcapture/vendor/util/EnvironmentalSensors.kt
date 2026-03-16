package com.trustcapture.vendor.util

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Snapshot of all environmental sensor readings at a point in time.
 */
data class EnvironmentalData(
    val pressureHpa: Float? = null,
    val altitudeMeters: Float? = null,
    val lightLux: Float? = null,
    val magneticX: Float? = null,
    val magneticY: Float? = null,
    val magneticZ: Float? = null,
    val magneticMagnitude: Float? = null,
    val tremorDetected: Boolean = false,
    val accelerometerMagnitude: Float? = null
)

/**
 * Collects environmental sensor data: barometer, ambient light,
 * magnetometer, and accelerometer (for hand tremor detection).
 *
 * Sensors are registered on subscribe and unregistered on cancel,
 * so battery usage is minimal when not actively capturing.
 *
 * Uses SENSOR_DELAY_UI for most sensors (slower updates, less CPU)
 * and SENSOR_DELAY_GAME only for accelerometer (tremor detection needs faster sampling).
 */
@Singleton
class EnvironmentalSensors @Inject constructor() {

    companion object {
        private const val TREMOR_THRESHOLD = 1.5f // m/s² deviation from gravity
        private const val EMIT_THROTTLE_MS = 200L // Throttle emissions to reduce recomposition
    }

    /**
     * Emits EnvironmentalData updates as sensor values change.
     * Registers all available sensors; missing sensors are null in the output.
     * Emissions are throttled to reduce UI recomposition overhead.
     */
    fun observe(context: Context): Flow<EnvironmentalData> = callbackFlow {
        val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager

        var pressure: Float? = null
        var light: Float? = null
        var magX: Float? = null
        var magY: Float? = null
        var magZ: Float? = null
        var accelMag: Float? = null
        var tremor = false
        var lastEmitTime = 0L

        val listener = object : SensorEventListener {
            override fun onSensorChanged(event: SensorEvent) {
                when (event.sensor.type) {
                    Sensor.TYPE_PRESSURE -> {
                        pressure = event.values[0]
                    }
                    Sensor.TYPE_LIGHT -> {
                        light = event.values[0]
                    }
                    Sensor.TYPE_MAGNETIC_FIELD -> {
                        magX = event.values[0]
                        magY = event.values[1]
                        magZ = event.values[2]
                    }
                    Sensor.TYPE_ACCELEROMETER -> {
                        val x = event.values[0]
                        val y = event.values[1]
                        val z = event.values[2]
                        val mag = kotlin.math.sqrt(x * x + y * y + z * z)
                        accelMag = mag
                        // Tremor = significant deviation from gravity (9.81 m/s²)
                        tremor = kotlin.math.abs(mag - SensorManager.GRAVITY_EARTH) > TREMOR_THRESHOLD
                    }
                }

                // Throttle emissions to reduce CPU/UI overhead
                val now = System.currentTimeMillis()
                if (now - lastEmitTime < EMIT_THROTTLE_MS) return
                lastEmitTime = now

                val magMagnitude = if (magX != null && magY != null && magZ != null) {
                    kotlin.math.sqrt(magX!! * magX!! + magY!! * magY!! + magZ!! * magZ!!)
                } else null

                val altitude = pressure?.let {
                    SensorManager.getAltitude(SensorManager.PRESSURE_STANDARD_ATMOSPHERE, it)
                }

                trySend(
                    EnvironmentalData(
                        pressureHpa = pressure,
                        altitudeMeters = altitude,
                        lightLux = light,
                        magneticX = magX,
                        magneticY = magY,
                        magneticZ = magZ,
                        magneticMagnitude = magMagnitude,
                        tremorDetected = tremor,
                        accelerometerMagnitude = accelMag
                    )
                )
            }

            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
        }

        // Register all available sensors with appropriate delays
        // SENSOR_DELAY_UI (~60ms) for most sensors — sufficient for display
        // SENSOR_DELAY_GAME (~20ms) for accelerometer — needed for tremor detection
        val barometer = sensorManager.getDefaultSensor(Sensor.TYPE_PRESSURE)
        val lightSensor = sensorManager.getDefaultSensor(Sensor.TYPE_LIGHT)
        val magnetometer = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)
        val accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)

        barometer?.let {
            sensorManager.registerListener(listener, it, SensorManager.SENSOR_DELAY_UI)
        }
        lightSensor?.let {
            sensorManager.registerListener(listener, it, SensorManager.SENSOR_DELAY_UI)
        }
        magnetometer?.let {
            sensorManager.registerListener(listener, it, SensorManager.SENSOR_DELAY_UI)
        }
        accelerometer?.let {
            sensorManager.registerListener(listener, it, SensorManager.SENSOR_DELAY_GAME)
        }

        awaitClose {
            sensorManager.unregisterListener(listener)
        }
    }
}
