package com.trustcapture.vendor.domain.gdpr

import android.content.Context
import com.google.gson.GsonBuilder
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.trustcapture.vendor.data.local.db.AuditDao
import com.trustcapture.vendor.data.local.db.PhotoDao
import com.trustcapture.vendor.data.local.datastore.UserPreferences
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import javax.inject.Inject
import javax.inject.Singleton

/**
 * GDPR compliance manager (Req 24.1-24.7).
 * Handles data export (JSON), data deletion, and vendor ID anonymization.
 */
@Singleton
class GdprManager @Inject constructor(
    private val photoDao: PhotoDao,
    private val auditDao: AuditDao,
    private val userPreferences: UserPreferences,
    @ApplicationContext private val context: Context
) {
    private val gson = GsonBuilder().setPrettyPrinting().create()
    private val isoFormatter = DateTimeFormatter.ISO_INSTANT.withZone(ZoneOffset.UTC)

    /**
     * Export all user data as a JSON file (Req 24.3).
     * Returns the file path of the exported JSON.
     */
    suspend fun exportUserData(): File = withContext(Dispatchers.IO) {
        val vendorId = userPreferences.vendorId.first() ?: "unknown"
        val privacyMode = userPreferences.privacyModeEnabled.first()
        val displayId = if (privacyMode) anonymize(vendorId) else vendorId

        val root = JsonObject()
        root.addProperty("export_date", isoFormatter.format(Instant.now()))
        root.addProperty("vendor_id", displayId)
        root.addProperty("privacy_mode", privacyMode)

        // Photos
        val photos = photoDao.getAllForVendor(vendorId)
        val photosArray = JsonArray()
        for (p in photos) {
            val obj = JsonObject()
            obj.addProperty("id", p.id)
            obj.addProperty("campaign_id", p.campaignId)
            obj.addProperty("campaign_code", p.campaignCode)
            obj.addProperty("campaign_type", p.campaignType)
            obj.addProperty("latitude", p.latitude)
            obj.addProperty("longitude", p.longitude)
            obj.addProperty("confidence_score", p.confidenceScore)
            obj.addProperty("upload_status", p.uploadStatus)
            obj.addProperty("captured_at", isoFormatter.format(Instant.ofEpochMilli(p.capturedAt)))
            obj.addProperty("emulator_mode", p.emulatorMode)
            photosArray.add(obj)
        }
        root.add("photos", photosArray)

        // Audit logs
        val audits = auditDao.getAllForVendor(vendorId)
        val auditsArray = JsonArray()
        for (a in audits) {
            val obj = JsonObject()
            obj.addProperty("id", a.id)
            obj.addProperty("event_type", a.eventType)
            obj.addProperty("photo_id", a.photoId)
            obj.addProperty("details", a.details)
            obj.addProperty("emulator_mode", a.emulatorMode)
            obj.addProperty("timestamp", isoFormatter.format(Instant.ofEpochMilli(a.timestamp)))
            auditsArray.add(obj)
        }
        root.add("audit_logs", auditsArray)

        val exportDir = File(context.filesDir, "gdpr_exports")
        exportDir.mkdirs()
        val exportFile = File(exportDir, "trustcapture_export_${System.currentTimeMillis()}.json")
        exportFile.writeText(gson.toJson(root))
        exportFile
    }

    /**
     * Delete all local user data (Req 24.4).
     * Clears photos, audit logs, and preferences.
     */
    suspend fun deleteAllUserData() = withContext(Dispatchers.IO) {
        val vendorId = userPreferences.vendorId.first() ?: return@withContext
        photoDao.deleteAllForVendor(vendorId)
        auditDao.deleteAllForVendor(vendorId)
        // Clear encrypted photo files
        val encDir = File(context.filesDir, "encrypted_photos")
        if (encDir.exists()) encDir.deleteRecursively()
        // Clear GDPR exports
        val exportDir = File(context.filesDir, "gdpr_exports")
        if (exportDir.exists()) exportDir.deleteRecursively()
        // Clear preferences (logs user out)
        userPreferences.clear()
    }

    /** SHA-256 hash of vendor ID for anonymization (Req 24.6) */
    private fun anonymize(vendorId: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(vendorId.toByteArray())
        return "anon_" + hash.take(8).joinToString("") { "%02x".format(it) }
    }
}
