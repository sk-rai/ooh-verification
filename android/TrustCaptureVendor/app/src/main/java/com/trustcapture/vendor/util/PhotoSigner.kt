package com.trustcapture.vendor.util

import android.content.Context
import android.net.Uri
import android.provider.Settings
import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import java.io.InputStream
import java.security.MessageDigest
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Signature payload matching backend's expected schema:
 * {
 *   "signature": "base64encodedstring",
 *   "algorithm": "ECDSA-SHA256",
 *   "device_id": "android-device-uuid",
 *   "timestamp": "2026-03-15T14:30:00Z",
 *   "location_hash": "sha256hashstring"
 * }
 */
data class SignaturePayload(
    @SerializedName("signature") val signature: String,
    @SerializedName("algorithm") val algorithm: String = "ECDSA-SHA256",
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("timestamp") val timestamp: String,
    @SerializedName("location_hash") val locationHash: String
)

@Singleton
class PhotoSigner @Inject constructor(
    private val keystoreManager: KeystoreManager
) {
    private val gson = Gson()

    /**
     * Signs a photo and produces the signature JSON string for upload.
     *
     * The signing process:
     * 1. Read photo bytes and compute SHA-256 hash
     * 2. Generate location hash from GPS coordinates
     * 3. Combine photo hash + location hash + timestamp into signing payload
     * 4. Sign the combined payload with the device's ECDSA private key
     * 5. Return the SignaturePayload as a JSON string
     */
    fun signPhoto(
        context: Context,
        photoUri: Uri,
        latitude: Double?,
        longitude: Double?,
        timestamp: Instant = Instant.now()
    ): String? {
        keystoreManager.generateKeyPairIfNeeded()

        // 1. Hash the photo bytes
        val photoHash = hashPhotoFromUri(context, photoUri) ?: return null

        // 2. Generate location hash
        val locationHash = generateLocationHash(latitude, longitude, timestamp)

        // 3. Build the data to sign: photoHash + locationHash + timestamp
        val timestampStr = DateTimeFormatter.ISO_INSTANT
            .withZone(ZoneOffset.UTC)
            .format(timestamp)
        val dataToSign = "$photoHash|$locationHash|$timestampStr"

        // 4. Sign with Keystore
        val signature = keystoreManager.sign(dataToSign.toByteArray()) ?: return null

        // 5. Build payload
        val deviceId = Settings.Secure.getString(
            context.contentResolver, Settings.Secure.ANDROID_ID
        )

        val payload = SignaturePayload(
            signature = signature,
            deviceId = deviceId,
            timestamp = timestampStr,
            locationHash = locationHash
        )

        return gson.toJson(payload)
    }

    /**
     * Generates a SHA-256 hash of the photo file contents.
     */
    private fun hashPhotoFromUri(context: Context, uri: Uri): String? {
        return try {
            val inputStream: InputStream = context.contentResolver.openInputStream(uri)
                ?: return null
            val digest = MessageDigest.getInstance("SHA-256")
            val buffer = ByteArray(8192)
            var bytesRead: Int
            while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                digest.update(buffer, 0, bytesRead)
            }
            inputStream.close()
            digest.digest().joinToString("") { "%02x".format(it) }
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Generates a SHA-256 location hash from GPS + timestamp.
     * This hash is included in the signature to bind location to the photo.
     */
    private fun generateLocationHash(
        latitude: Double?,
        longitude: Double?,
        timestamp: Instant
    ): String {
        val data = buildString {
            append("lat:${latitude ?: 0.0}|")
            append("lon:${longitude ?: 0.0}|")
            append("ts:${timestamp.epochSecond}")
        }
        val digest = MessageDigest.getInstance("SHA-256")
        return digest.digest(data.toByteArray()).joinToString("") { "%02x".format(it) }
    }

    /**
     * Verifies a signature locally (for testing/debugging).
     */
    fun verifySignature(
        context: Context,
        photoUri: Uri,
        signatureJson: String,
        latitude: Double?,
        longitude: Double?
    ): Boolean {
        val payload = gson.fromJson(signatureJson, SignaturePayload::class.java)
        val timestamp = Instant.parse(payload.timestamp)
        val locationHash = generateLocationHash(latitude, longitude, timestamp)
        val photoHash = hashPhotoFromUri(context, photoUri) ?: return false
        val dataToVerify = "$photoHash|$locationHash|${payload.timestamp}"
        return keystoreManager.verify(dataToVerify.toByteArray(), payload.signature)
    }
}
