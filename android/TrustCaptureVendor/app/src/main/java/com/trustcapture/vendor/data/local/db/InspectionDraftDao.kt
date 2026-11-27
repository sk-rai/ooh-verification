package com.trustcapture.vendor.data.local.db

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Entity(
    tableName = "inspection_draft_answers",
    primaryKeys = ["tenantId", "vendorId", "ownerClientId", "visitId", "assignmentId", "generation",
        "documentInstanceId", "repeatItemId", "fieldId"]
)
data class InspectionDraftAnswer(
    val tenantId: String,
    val vendorId: String,
    val ownerClientId: String,
    val visitId: String,
    val assignmentId: String,
    val generation: Long,
    val documentInstanceId: String,
    val repeatItemId: String,
    val fieldId: String,
    val value: String
)

@Entity(
    tableName = "inspection_packages",
    primaryKeys = ["tenantId", "vendorId", "ownerClientId", "visitId", "assignmentId", "generation"]
)
data class InspectionCachedPackage(
    val tenantId: String,
    val vendorId: String,
    val ownerClientId: String,
    val visitId: String,
    val assignmentId: String,
    val generation: Long,
    val packageJson: String
)

@Dao
interface InspectionDraftDao {
    @Query(
        """
        SELECT * FROM inspection_packages WHERE tenantId = :tenantId AND vendorId = :vendorId
          AND ownerClientId = :ownerClientId AND visitId = :visitId
          AND assignmentId = :assignmentId AND generation = :generation
        """
    )
    suspend fun readPackage(
        tenantId: String,
        vendorId: String,
        ownerClientId: String,
        visitId: String,
        assignmentId: String,
        generation: Long
    ): InspectionCachedPackage?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun savePackage(value: InspectionCachedPackage)

    @Query(
        """
        DELETE FROM inspection_packages WHERE tenantId = :tenantId AND vendorId = :vendorId
          AND ownerClientId = :ownerClientId AND visitId = :visitId
          AND assignmentId = :assignmentId AND generation = :generation
        """
    )
    suspend fun removePackage(
        tenantId: String,
        vendorId: String,
        ownerClientId: String,
        visitId: String,
        assignmentId: String,
        generation: Long
    )

    @Query(
        """
        SELECT * FROM inspection_draft_answers
        WHERE tenantId = :tenantId AND vendorId = :vendorId AND ownerClientId = :ownerClientId
          AND visitId = :visitId AND assignmentId = :assignmentId AND generation = :generation
          AND documentInstanceId = :documentInstanceId
        """
    )
    suspend fun readAnswers(
        tenantId: String,
        vendorId: String,
        ownerClientId: String,
        visitId: String,
        assignmentId: String,
        generation: Long,
        documentInstanceId: String
    ): List<InspectionDraftAnswer>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun saveAnswer(answer: InspectionDraftAnswer)
}

val INSPECTION_DRAFT_MIGRATION_10_11 = object : Migration(10, 11) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE inspection_draft_answers (
                tenantId TEXT NOT NULL,
                vendorId TEXT NOT NULL,
                ownerClientId TEXT NOT NULL,
                visitId TEXT NOT NULL,
                assignmentId TEXT NOT NULL,
                generation INTEGER NOT NULL,
                documentInstanceId TEXT NOT NULL,
                repeatItemId TEXT NOT NULL,
                fieldId TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (tenantId, vendorId, ownerClientId, visitId, assignmentId, generation,
                             documentInstanceId, repeatItemId, fieldId)
            )
            """.trimIndent()
        )
        db.execSQL(
            """
            CREATE TABLE inspection_packages (
                tenantId TEXT NOT NULL, vendorId TEXT NOT NULL, ownerClientId TEXT NOT NULL,
                visitId TEXT NOT NULL, assignmentId TEXT NOT NULL, generation INTEGER NOT NULL,
                packageJson TEXT NOT NULL,
                PRIMARY KEY (tenantId, vendorId, ownerClientId, visitId, assignmentId, generation)
            )
            """.trimIndent()
        )
        db.execSQL(
            """
            CREATE TABLE inspection_evidence_finalizations (
                tenantId TEXT NOT NULL, vendorId TEXT NOT NULL, reservationId TEXT NOT NULL,
                visitId TEXT NOT NULL, requestJson TEXT NOT NULL, mediaPath TEXT NOT NULL,
                receiptId TEXT, evidenceId TEXT, eligible INTEGER, held INTEGER NOT NULL,
                PRIMARY KEY (tenantId, vendorId, reservationId)
            )
            """.trimIndent()
        )
    }
}
