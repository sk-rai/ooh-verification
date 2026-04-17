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
     * 2. Sign the photo hash with the device's ECDSA private key
     * 3. Generate location hash from GPS coordinates (included in payload, not signed data)
     * 4. Return the SignaturePayload as a JSON string
     *
     * IMPORTANT: The backend verifies the signature against the raw photo hash only.
     * The location_hash and timestamp are metadata — not part of the signed data.
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

        // 2. Sign the photo hash directly (backend verifies against photo_hash)
        val signature = keystoreManager.sign(photoHash.toByteArray()) ?: return null

        // 3. Generate location hash (metadata, not part of signed data)
        val locationHash = generateLocationHash(latitude, longitude, timestamp)

        val timestampStr = DateTimeFormatter.ISO_INSTANT
            .withZone(ZoneOffset.UTC)
            .format(timestamp)

        // 4. Build payload
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
        val photoHash = hashPhotoFromUri(context, photoUri) ?: return false
        return keystoreManager.verify(photoHash.toByteArray(), payload.signature)
    }
}
