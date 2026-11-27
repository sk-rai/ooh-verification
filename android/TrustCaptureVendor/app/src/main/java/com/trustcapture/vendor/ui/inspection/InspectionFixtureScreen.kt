package com.trustcapture.vendor.ui.inspection

import android.util.Log
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.google.gson.Gson
import com.google.gson.JsonParseException
import com.trustcapture.vendor.data.local.db.InspectionCachedPackage
import com.trustcapture.vendor.data.local.db.InspectionDraftAnswer
import com.trustcapture.vendor.data.local.db.InspectionDraftDao
import com.trustcapture.vendor.data.remote.api.InspectionVisitApi
import com.trustcapture.vendor.data.remote.dto.InspectionPackageDto
import com.trustcapture.vendor.data.remote.dto.InspectionPackageDocumentDto
import com.trustcapture.vendor.data.remote.dto.InspectionCaptureTargetDto
import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout

data class InspectionFixtureAssignment(
    val visitId: String,
    val ownerClientId: String,
    val assignmentId: String,
    val generation: Long
)

@Composable
fun InspectionFixtureScreen(
    assignment: InspectionFixtureAssignment,
    stagingApi: InspectionVisitApi,
    draftDao: InspectionDraftDao,
    tenantId: String,
    vendorId: String,
    modifier: Modifier = Modifier,
    expectedRequiredPhotoOnSecondItem: String? = null,
    onCapture: ((String, InspectionCaptureTargetDto) -> Unit)? = null,
    offlineOnly: Boolean = false
) {
    // Retrofit service proxies do not provide stable equality for Compose keys.
    var document by remember(assignment, tenantId, vendorId) {
        mutableStateOf<InspectionPackageDocumentDto?>(null)
    }
    var message by remember(assignment, tenantId, vendorId) { mutableStateOf("Loading inspection…") }
    var saveFailed by remember(assignment, tenantId, vendorId) { mutableStateOf(false) }
    var loadAttempt by remember(assignment, tenantId, vendorId) { mutableStateOf(0) }
    var loading by remember(assignment, tenantId, vendorId) { mutableStateOf(true) }
    val answers = remember(assignment, tenantId, vendorId) {
        mutableStateMapOf<InspectionAnswerKey, String>()
    }
    val saveLock = remember { Mutex() }
    val gson = remember { Gson() }
    val scope = rememberCoroutineScope()
    LaunchedEffect(assignment, tenantId, vendorId, expectedRequiredPhotoOnSecondItem, loadAttempt, offlineOnly) {
        Log.d("Gate1Package", "Package effect started")
        loading = true
        message = "Loading inspection package…"
        var phase = "package fetch"
        try {
            val response = if (offlineOnly) null else try {
                stagingApi.getPackage(
                    assignment.visitId, assignment.ownerClientId, assignment.assignmentId, assignment.generation
                )
            } catch (_: IOException) {
                null
            }
            if (response != null && !response.isSuccessful) {
                message = "Inspection request failed (HTTP ${response.code()})."
                if (response.code() in setOf(401, 403, 404, 409, 410)) {
                    phase = "cached package invalidation"
                    withTimeout(15_000) {
                        draftDao.removePackage(
                            tenantId, vendorId, assignment.ownerClientId, assignment.visitId,
                            assignment.assignmentId, assignment.generation
                        )
                    }
                }
                return@LaunchedEffect
            }
            val body = if (response == null) {
                phase = "cached package read"
                message = "Reading the cached inspection package…"
                withTimeout(15_000) {
                    draftDao.readPackage(
                        tenantId, vendorId, assignment.ownerClientId, assignment.visitId,
                        assignment.assignmentId, assignment.generation
                    )?.let { gson.fromJson(it.packageJson, InspectionPackageDto::class.java) }
                }
            } else response.body()
            Log.d("Gate1Package", "Package response decoded: HTTP ${response?.code() ?: "offline"}")
            phase = "package validation"
            if (body == null) {
                message = if (response == null) "No saved inspection is available offline." else "Unable to load this inspection."
            } else if (body.tenantId != tenantId || body.vendorId != vendorId ||
                body.visitId != assignment.visitId || body.ownerClientId != assignment.ownerClientId ||
                body.assignmentId != assignment.assignmentId || body.generation != assignment.generation
            ) {
                message = "The returned inspection does not match the assignment."
            } else {
                val pinned = body.documents.singleOrNull().takeIf { body.code == "PACKAGE_READY" }
                if (pinned == null) {
                    message = "This inspection form is unsupported."
                    phase = "cached package invalidation"
                    withTimeout(15_000) {
                        draftDao.removePackage(
                            tenantId, vendorId, assignment.ownerClientId, assignment.visitId,
                            assignment.assignmentId, assignment.generation
                        )
                    }
                } else if (expectedRequiredPhotoOnSecondItem != null &&
                    (InspectionRepeatForm.parse(pinned.definition)?.itemIds?.getOrNull(1) != expectedRequiredPhotoOnSecondItem ||
                        pinned.captureTargets.none { it.required && it.repeatItemId == expectedRequiredPhotoOnSecondItem })
                ) {
                    message = "Package loaded, but the expected required photo on item two was missing."
                } else {
                    if (response != null) {
                        phase = "package cache write"
                        message = "Package received. Saving it on this device…"
                        withTimeout(15_000) {
                            draftDao.savePackage(
                                InspectionCachedPackage(
                                    tenantId, vendorId, assignment.ownerClientId, assignment.visitId,
                                    assignment.assignmentId, assignment.generation, gson.toJson(body)
                                )
                            )
                        }
                        Log.d("Gate1Package", "Package cached")
                    }
                    phase = "saved answer read"
                    message = "Reading saved inspection answers…"
                    val saved = withTimeout(15_000) {
                        draftDao.readAnswers(
                            tenantId, vendorId, assignment.ownerClientId, assignment.visitId,
                            assignment.assignmentId, assignment.generation, pinned.id
                        )
                    }
                    saved.forEach { answers[InspectionAnswerKey(it.repeatItemId, it.fieldId)] = it.value }
                    document = pinned
                    Log.d("Gate1Package", "Inspection ready to render")
                }
            }
        } catch (_: TimeoutCancellationException) {
            message = "Inspection timed out during $phase."
        } catch (cancelled: CancellationException) {
            Log.d("Gate1Package", "Package effect cancelled")
            throw cancelled
        } catch (_: JsonParseException) {
            message = "The inspection package could not be read."
        } catch (error: RuntimeException) {
            message = "Inspection failed during $phase (${error.javaClass.simpleName})."
        } finally {
            loading = false
        }
    }

    val readyDocument = document
    if (readyDocument == null) {
        Column(modifier) {
            Text(message)
            if (!loading) TextButton(onClick = { loadAttempt++ }) { Text("Retry inspection") }
        }
    } else {
        Column(modifier) {
            if (offlineOnly) Text("Saved inspection · read only until you sign in.")
            if (expectedRequiredPhotoOnSecondItem != null) Text("Required photo is on item two.")
            if (saveFailed) Text("A draft edit could not be saved. Edit the field again before leaving.")
            InspectionForm(readyDocument, answers, { key, answer ->
                answers[key] = answer
                scope.launch {
                    saveLock.withLock {
                        try {
                            draftDao.saveAnswer(
                                InspectionDraftAnswer(
                                    tenantId, vendorId, assignment.ownerClientId, assignment.visitId,
                                    assignment.assignmentId, assignment.generation, readyDocument.id,
                                    key.repeatItemId, key.fieldId, answer
                                )
                            )
                        } catch (_: android.database.SQLException) {
                            saveFailed = true
                        }
                    }
                }
            }, Modifier.weight(1f), onCapture?.let { capture -> { target -> capture(readyDocument.id, target) } },
                readOnly = offlineOnly)
        }
    }
}
