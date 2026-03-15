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
 */
@Singleton
class EnvironmentalSensors @Inject constructor() {

    companion object {
        private const val TREMOR_THRESHOLD = 1.5f // m/s² deviation from gravity
    }

    /**
     * Emits EnvironmentalData updates as sensor values change.
     * Registers all available sensors; missing sensors are null in the output.
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

        // Register all available sensors
        val barometer = sensorManager.getDefaultSensor(Sensor.TYPE_PRESSURE)
        val lightSensor = sensorManager.getDefaultSensor(Sensor.TYPE_LIGHT)
        val magnetometer = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)
        val accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)

        barometer?.let {
            sensorManager.registerListener(listener, it, SensorManager.SENSOR_DELAY_NORMAL)
        }
        lightSensor?.let {
            sensorManager.registerListener(listener, it, SensorManager.SENSOR_DELAY_NORMAL)
        }
        magnetometer?.let {
            sensorManager.registerListener(listener, it, SensorManager.SENSOR_DELAY_NORMAL)
        }
        accelerometer?.let {
            sensorManager.registerListener(listener, it, SensorManager.SENSOR_DELAY_GAME)
        }

        awaitClose {
            sensorManager.unregisterListener(listener)
        }
    }
}
