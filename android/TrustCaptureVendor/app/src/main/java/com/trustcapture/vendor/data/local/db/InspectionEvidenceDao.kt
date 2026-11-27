package com.trustcapture.vendor.data.local.db

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.ColumnInfo
import androidx.room.Query
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Entity(tableName = "inspection_pending_captures")
data class InspectionPendingCapture(
    @androidx.room.PrimaryKey val captureId: String,
    val tenantId: String,
    val vendorId: String,
    val visitId: String,
    val mediaPath: String,
    val reservationJson: String,
    val keyId: String,
    val signature: String,
    val reservationId: String? = null,
    @ColumnInfo(defaultValue = "0") val originalStored: Boolean = false,
    @ColumnInfo(defaultValue = "0") val held: Boolean = false
)

val INSPECTION_CAPTURE_MIGRATION_12_13 = object : Migration(12, 13) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("ALTER TABLE inspection_pending_captures ADD COLUMN reservationId TEXT")
        db.execSQL("ALTER TABLE inspection_pending_captures ADD COLUMN originalStored INTEGER NOT NULL DEFAULT 0")
        db.execSQL("ALTER TABLE inspection_pending_captures ADD COLUMN held INTEGER NOT NULL DEFAULT 0")
    }
}

val INSPECTION_CAPTURE_MIGRATION_11_12 = object : Migration(11, 12) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE inspection_pending_captures (
                captureId TEXT NOT NULL PRIMARY KEY, tenantId TEXT NOT NULL, vendorId TEXT NOT NULL,
                visitId TEXT NOT NULL, mediaPath TEXT NOT NULL, reservationJson TEXT NOT NULL,
                keyId TEXT NOT NULL, signature TEXT NOT NULL
            )
            """.trimIndent()
        )
    }
}

@Entity(tableName = "inspection_evidence_finalizations", primaryKeys = ["tenantId", "vendorId", "reservationId"])
data class InspectionEvidenceFinalizationRow(
    val tenantId: String,
    val vendorId: String,
    val reservationId: String,
    val visitId: String,
    val requestJson: String,
    val mediaPath: String,
    val receiptId: String? = null,
    val evidenceId: String? = null,
    val eligible: Boolean? = null,
    val held: Boolean = false
)

@Dao
interface InspectionEvidenceDao {
    @Insert
    suspend fun insertPendingCapture(row: InspectionPendingCapture)

    @Query("SELECT * FROM inspection_pending_captures WHERE tenantId = :tenantId AND vendorId = :vendorId AND visitId = :visitId")
    suspend fun readCaptures(tenantId: String, vendorId: String, visitId: String): List<InspectionPendingCapture>

    @Query("UPDATE inspection_pending_captures SET reservationId = :reservationId WHERE captureId = :captureId AND reservationId IS NULL")
    suspend fun recordReservation(captureId: String, reservationId: String): Int

    @Query("UPDATE inspection_pending_captures SET originalStored = 1 WHERE captureId = :captureId AND reservationId = :reservationId")
    suspend fun recordOriginal(captureId: String, reservationId: String): Int

    @Query("UPDATE inspection_pending_captures SET held = 1 WHERE captureId = :captureId")
    suspend fun holdCapture(captureId: String)

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(row: InspectionEvidenceFinalizationRow)

    @Query(
        """
        SELECT * FROM inspection_evidence_finalizations
        WHERE tenantId = :tenantId AND vendorId = :vendorId AND reservationId = :reservationId
        """
    )
    suspend fun read(tenantId: String, vendorId: String, reservationId: String): InspectionEvidenceFinalizationRow?

    @Query(
        """
        UPDATE inspection_evidence_finalizations
        SET receiptId = :receiptId, evidenceId = :evidenceId, eligible = :eligible
        WHERE tenantId = :tenantId AND vendorId = :vendorId AND reservationId = :reservationId
          AND requestJson = :requestJson AND evidenceId IS NULL AND held = 0
        """
    )
    suspend fun acknowledge(
        tenantId: String, vendorId: String, reservationId: String, requestJson: String,
        receiptId: String, evidenceId: String, eligible: Boolean
    ): Int

    @Query(
        """
        UPDATE inspection_evidence_finalizations SET held = 1
        WHERE tenantId = :tenantId AND vendorId = :vendorId AND reservationId = :reservationId
          AND requestJson = :requestJson AND evidenceId IS NULL
        """
    )
    suspend fun hold(tenantId: String, vendorId: String, reservationId: String, requestJson: String)
}
