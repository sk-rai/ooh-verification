package com.trustcapture.vendor.util

import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.PrivateKey
import java.security.PublicKey
import java.security.Signature
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages hardware-backed cryptographic keys via Android Keystore.
 *
 * Generates an ECDSA P-256 key pair on first use, stored in the Keystore
 * with hardware backing (StrongBox when available). The private key never
 * leaves the secure hardware — only signing operations are performed.
 *
 * The public key is exported in PEM format for server-side registration
 * and signature verification.
 */
@Singleton
class KeystoreManager @Inject constructor() {

    companion object {
        private const val KEYSTORE_PROVIDER = "AndroidKeyStore"
        private const val KEY_ALIAS = "trustcapture_device_key"
        private const val SIGNATURE_ALGORITHM = "SHA256withECDSA"
    }

    private val keyStore: KeyStore by lazy {
        KeyStore.getInstance(KEYSTORE_PROVIDER).apply { load(null) }
    }

    /**
     * Returns true if a key pair already exists in the Keystore.
     */
    fun hasKeyPair(): Boolean {
        return keyStore.containsAlias(KEY_ALIAS)
    }

    /**
     * Generates an ECDSA P-256 key pair in the Android Keystore.
     * Uses StrongBox (hardware security module) on supported devices.
     * No-op if key already exists.
     */
    fun generateKeyPairIfNeeded() {
        if (hasKeyPair()) return

        try {
            generateKeyPair(useStrongBox = true)
        } catch (e: Exception) {
            // StrongBox not available — fall back to TEE-backed key
            generateKeyPair(useStrongBox = false)
        }
    }

    private fun generateKeyPair(useStrongBox: Boolean) {
        val builder = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
        )
            .setAlgorithmParameterSpec(
                java.security.spec.ECGenParameterSpec("secp256r1")
            )
            .setDigests(KeyProperties.DIGEST_SHA256)
            .setUserAuthenticationRequired(false) // Don't require biometric for each sign

        if (useStrongBox && Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            builder.setIsStrongBoxBacked(true)
        }

        val keyPairGenerator = KeyPairGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_EC,
            KEYSTORE_PROVIDER
        )
        keyPairGenerator.initialize(builder.build())
        keyPairGenerator.generateKeyPair()
    }

    /**
     * Returns the public key in PEM format for server registration.
     * Format: "-----BEGIN PUBLIC KEY-----\n<base64>\n-----END PUBLIC KEY-----"
     */
    fun getPublicKeyPem(): String? {
        val publicKey = getPublicKey() ?: return null
        val encoded = Base64.encodeToString(publicKey.encoded, Base64.NO_WRAP)
        return "-----BEGIN PUBLIC KEY-----\n$encoded\n-----END PUBLIC KEY-----"
    }

    /**
     * Returns the raw public key bytes (X.509 SubjectPublicKeyInfo DER encoding).
     */
    fun getPublicKey(): PublicKey? {
        return try {
            keyStore.getCertificate(KEY_ALIAS)?.publicKey
        } catch (e: Exception) {
            null
        }
    }

    private fun getPrivateKey(): PrivateKey? {
        return try {
            keyStore.getKey(KEY_ALIAS, null) as? PrivateKey
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Signs arbitrary data with the device's private key using SHA256withECDSA.
     * Returns Base64-encoded signature string, or null on failure.
     */
    fun sign(data: ByteArray): String? {
        val privateKey = getPrivateKey() ?: return null
        return try {
            val signature = Signature.getInstance(SIGNATURE_ALGORITHM)
            signature.initSign(privateKey)
            signature.update(data)
            val signedBytes = signature.sign()
            Base64.encodeToString(signedBytes, Base64.NO_WRAP)
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Verifies a signature against data using the device's public key.
     * Used for local verification / testing.
     */
    fun verify(data: ByteArray, signatureBase64: String): Boolean {
        val publicKey = getPublicKey() ?: return false
        return try {
            val signatureBytes = Base64.decode(signatureBase64, Base64.NO_WRAP)
            val sig = Signature.getInstance(SIGNATURE_ALGORITHM)
            sig.initVerify(publicKey)
            sig.update(data)
            sig.verify(signatureBytes)
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Returns info about the key for debugging/display.
     */
    fun getKeyInfo(): Map<String, String> {
        val info = mutableMapOf<String, String>()
        info["alias"] = KEY_ALIAS
        info["exists"] = hasKeyPair().toString()
        info["algorithm"] = "ECDSA P-256 (secp256r1)"
        info["signatureAlgorithm"] = SIGNATURE_ALGORITHM

        if (hasKeyPair()) {
            try {
                val key = keyStore.getKey(KEY_ALIAS, null) as? PrivateKey
                if (key != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    val factory = java.security.KeyFactory.getInstance(
                        key.algorithm, KEYSTORE_PROVIDER
                    )
                    val keyInfo = factory.getKeySpec(
                        key,
                        android.security.keystore.KeyInfo::class.java
                    )
                    info["insideSecureHardware"] = keyInfo.isInsideSecureHardware.toString()
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                        info["securityLevel"] = keyInfo.securityLevel.toString()
                    }
                }
            } catch (e: Exception) {
                info["hardwareInfo"] = "unavailable: ${e.message}"
            }
        }
        return info
    }

    /**
     * Deletes the key pair. Use with caution — the device will need
     * to re-register with the server after this.
     */
    fun deleteKeyPair() {
        if (hasKeyPair()) {
            keyStore.deleteEntry(KEY_ALIAS)
        }
    }
}
