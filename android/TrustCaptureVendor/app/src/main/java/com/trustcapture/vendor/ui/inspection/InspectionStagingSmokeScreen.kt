package com.trustcapture.vendor.ui.inspection

import android.content.Context
import android.provider.Settings
import android.util.Log
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.trustcapture.vendor.BuildConfig
import com.trustcapture.vendor.data.local.db.InspectionDraftDao
import com.trustcapture.vendor.data.local.db.InspectionEvidenceDao
import com.trustcapture.vendor.data.local.db.InspectionPendingCapture
import com.trustcapture.vendor.data.remote.api.AuthApi
import com.trustcapture.vendor.data.remote.api.InspectionVisitApi
import com.trustcapture.vendor.data.remote.dto.InspectionDeviceEnrollmentDto
import com.trustcapture.vendor.data.remote.dto.InspectionCaptureTargetDto
import com.trustcapture.vendor.data.remote.dto.OtpRequest
import com.trustcapture.vendor.data.remote.dto.OtpVerifyRequest
import com.trustcapture.vendor.util.KeystoreManager
import com.trustcapture.vendor.domain.repository.InspectionCaptureSync
import com.trustcapture.vendor.domain.repository.InspectionFinalizationOutcome
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import java.io.File
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.util.UUID
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import java.util.concurrent.atomic.AtomicBoolean
import javax.net.ssl.SSLException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

private const val TENANT = "6c3cd4bd-d26f-4a71-ac19-affda91106f4"
private const val VENDOR = "G06644"
private const val PHONE = "+15550106644"
private val assignment = InspectionFixtureAssignment(
    "1c0d7d57-a7ae-4d5e-a1f4-45a593752eb4",
    "621bcb97-32b6-4e8c-b13f-d87d08ca949b",
    "26572f2f-80c5-4383-acd2-95e78a71d82a",
    1
)

private class StagingSmokeSession {
    val token = AtomicReference<String?>()
    val dropNextFinalizationResponse = AtomicBoolean(false)
    private val retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.BASE_URL)
        .client(
            OkHttpClient.Builder()
                .connectTimeout(20, TimeUnit.SECONDS)
                .readTimeout(45, TimeUnit.SECONDS)
                .callTimeout(60, TimeUnit.SECONDS)
                .followRedirects(false)
                .followSslRedirects(false)
                .addInterceptor { chain ->
                    val request = chain.request()
                    check(request.url.isHttps && request.url.host == "tc-staging-rolecheck-probe.onrender.com")
                    val scoped = request.newBuilder().header("X-Tenant-ID", TENANT)
                    token.get()?.let { scoped.header("Authorization", "Bearer $it") }
                    val response = chain.proceed(scoped.build())
                    val segments = request.url.pathSegments
                    if (request.method == "POST" && segments.size == 6 &&
                        segments[0] == "api" && segments[1] == "inspection-visits" &&
                        segments[3] == "capture-reservations" && segments[5] == "finalize" &&
                        response.code == 201 && dropNextFinalizationResponse.compareAndSet(true, false)
                    ) {
                        response.close()
                        Log.i("Gate1Evidence", "Dropped committed finalization response; reservation=${segments[4]}")
                        throw IOException("Staging finalization response deliberately dropped.")
                    }
                    response
                }
                .build()
        )
        .addConverterFactory(GsonConverterFactory.create())
        .build()
    val auth: AuthApi = retrofit.create(AuthApi::class.java)
    val inspections: InspectionVisitApi = retrofit.create(InspectionVisitApi::class.java)
}

private data class StagingCapture(val id: String, val documentId: String, val target: InspectionCaptureTargetDto, val file: File)

@Composable
fun InspectionStagingSmokeScreen(
    draftDao: InspectionDraftDao,
    evidenceDao: InspectionEvidenceDao,
    keystore: KeystoreManager,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current.applicationContext
    val session = remember { StagingSmokeSession() }
    val captureSync = remember(session, evidenceDao) {
        InspectionCaptureSync(evidenceDao, session.inspections, File(context.filesDir, "inspection_media")) {
            Log.i("Gate1Evidence", it)
        }
    }
    val scope = rememberCoroutineScope()
    var otp by remember { mutableStateOf("") }
    var requested by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var signedIn by remember { mutableStateOf(false) }
    var enrolled by remember { mutableStateOf(false) }
    var offlineDraft by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("") }
    var capture by remember { mutableStateOf<StagingCapture?>(null) }
    var savingPhoto by remember { mutableStateOf(false) }
    var dropArmed by remember { mutableStateOf(false) }

    Column(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Gate 1 staging")
        if (message.isNotEmpty()) Text(message)
        val currentCapture = capture
        if (currentCapture != null) {
            if (savingPhoto) {
                Text("Saving inspection photo…")
            } else {
                InspectionOriginalCamera(currentCapture.file, onSaved = {
                    savingPhoto = true
                    scope.launch {
                        try {
                            queueStagingCapture(context, currentCapture, evidenceDao, keystore)
                            capture = null
                            message = "Photo saved on this device. Upload is pending."
                        } catch (cancelled: CancellationException) {
                            throw cancelled
                        } catch (_: IOException) {
                            capture = null
                            message = "Could not queue the inspection photo. Upload did not start."
                        } catch (_: RuntimeException) {
                            capture = null
                            message = "Could not queue the inspection photo. Upload did not start."
                        } finally {
                            savingPhoto = false
                        }
                    }
                }, onCancel = { capture = null })
            }
        } else if (offlineDraft) {
            Button(onClick = { offlineDraft = false }) { Text("Back to staging sign-in") }
            InspectionFixtureScreen(
                assignment, session.inspections, draftDao, TENANT, VENDOR, Modifier.weight(1f),
                expectedRequiredPhotoOnSecondItem = "470c1007-2979-499f-b5b4-e99e038bcbcb",
                offlineOnly = true
            )
        } else if (enrolled) {
            Button(enabled = !busy && !dropArmed, onClick = {
                session.dropNextFinalizationResponse.set(true)
                dropArmed = true
                message = "Next new finalization response will be dropped."
            }) { Text("Drop next finalization response") }
            Button(enabled = !busy, onClick = {
                busy = true
                scope.launch {
                    try {
                        val outcomes = captureSync.sync(
                            TENANT, VENDOR, assignment.visitId, assignment.ownerClientId,
                            assignment.assignmentId, assignment.generation
                        )
                        val complete = outcomes.count { it == InspectionFinalizationOutcome.COMPLETE }
                        val retry = outcomes.count { it == InspectionFinalizationOutcome.RETRY }
                        val held = outcomes.count { it == InspectionFinalizationOutcome.HOLD }
                        message = if (outcomes.isEmpty()) "No saved inspection photos."
                            else "Photo sync: $complete complete, $retry pending retry, $held held."
                    } catch (cancelled: CancellationException) {
                        throw cancelled
                    } catch (_: RuntimeException) {
                        message = "Photo sync could not finish. Check the local queue before retrying."
                    } finally {
                        dropArmed = session.dropNextFinalizationResponse.get()
                        busy = false
                    }
                }
            }) { Text("Sync saved photos") }
            InspectionFixtureScreen(
                assignment, session.inspections, draftDao, TENANT, VENDOR, Modifier.weight(1f),
                expectedRequiredPhotoOnSecondItem = "470c1007-2979-499f-b5b4-e99e038bcbcb",
                onCapture = if (busy) null else { documentId, target ->
                    val directory = File(context.filesDir, "inspection_media")
                    if (directory.isDirectory || directory.mkdirs()) {
                        val id = UUID.randomUUID().toString()
                        capture = StagingCapture(id, documentId, target, File(directory, "$id.jpg"))
                    } else {
                        message = "Could not prepare local photo storage."
                    }
                }
            )
        } else {
            Button(enabled = !busy, onClick = {
                busy = true
                scope.launch {
                    try {
                        offlineDraft = withContext(Dispatchers.IO) {
                            val enrollment = context.getSharedPreferences("gate1_staging_enrollment", Context.MODE_PRIVATE)
                            val deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
                            val fingerprint = keystore.getPublicKeyFingerprint()
                            enrollment.getString("tenant_id", null) == TENANT &&
                                enrollment.getString("vendor_id", null) == VENDOR &&
                                enrollment.getString("device_id", null) == deviceId &&
                                !enrollment.getString("key_id", null).isNullOrBlank() &&
                                fingerprint != null && enrollment.getString("key_fingerprint", null) == fingerprint
                        }
                        message = if (offlineDraft) "" else "No matching staging enrollment is saved. Sign in to open the inspection."
                    } finally {
                        busy = false
                    }
                }
            }) { Text("Open saved inspection") }
            Button(enabled = !busy, onClick = {
                busy = true
                scope.launch {
                    try {
                        session.token.set(null)
                        requested = false
                        signedIn = false
                        val response = session.auth.requestOtp(OtpRequest(PHONE, VENDOR))
                        requested = response.isSuccessful
                        message = if (requested) "OTP requested. Ask the staging operator for the code."
                            else "OTP request failed (HTTP ${response.code()})."
                    } catch (error: IOException) {
                        message = "OTP request: ${stagingConnectionMessage(error)}"
                    } finally {
                        busy = false
                    }
                }
            }) { Text("Request staging OTP") }
            if (requested) {
                OutlinedTextField(
                    value = otp, onValueChange = { otp = it }, label = { Text("OTP") },
                    visualTransformation = PasswordVisualTransformation(), singleLine = true,
                    modifier = Modifier.fillMaxWidth(), enabled = !busy
                )
                Button(enabled = !busy && otp.isNotBlank(), onClick = {
                    val code = otp.trim()
                    otp = ""
                    busy = true
                    scope.launch {
                        try {
                            val deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
                            val verification = session.auth.verifyOtp(OtpVerifyRequest(PHONE, VENDOR, code, deviceId, true))
                            val auth = verification.body()
                            if (!verification.isSuccessful || auth?.accessToken.isNullOrBlank()) {
                                message = "Sign-in failed (HTTP ${verification.code()})."
                                return@launch
                            }
                            signedIn = true
                            val proof = auth?.inspectionEnrollmentProof
                            if (proof.isNullOrBlank()) {
                                message = "Sign-in passed. Enrollment proof was missing."
                                return@launch
                            }
                            session.token.set(requireNotNull(auth).accessToken)
                            enrolled = enrollStagingKey(context, session.inspections, keystore, deviceId, proof)
                            message = if (enrolled) "Sign-in and device enrollment passed."
                                else "Sign-in passed. Device enrollment failed. Request a fresh OTP before retrying."
                        } catch (error: IOException) {
                            val phase = if (signedIn) "Sign-in passed. Enrollment" else "OTP verification"
                            message = "$phase: ${stagingConnectionMessage(error)}"
                        } finally {
                            busy = false
                        }
                    }
                }) { Text("Verify OTP and enroll") }
            }
        }
    }
}

private suspend fun queueStagingCapture(
    context: Context,
    capture: StagingCapture,
    dao: InspectionEvidenceDao,
    keystore: KeystoreManager
) = withContext(Dispatchers.IO) {
    val enrollment = context.getSharedPreferences("gate1_staging_enrollment", Context.MODE_PRIVATE)
    val keyId = enrollment.getString("key_id", null)
    val fingerprint = keystore.getPublicKeyFingerprint()
    if (keyId.isNullOrBlank() || fingerprint == null || fingerprint != enrollment.getString("key_fingerprint", null) ||
        enrollment.getString("tenant_id", null) != TENANT || enrollment.getString("vendor_id", null) != VENDOR
    ) throw IOException("Enrollment no longer matches the current key.")
    val length = capture.file.length()
    if (length !in 1L..10_485_760L) throw IOException("Original exceeds the capture size limit.")
    val sha256 = MessageDigest.getInstance("SHA-256")
    capture.file.inputStream().buffered().use { input ->
        val buffer = ByteArray(8192)
        while (true) {
            val count = input.read(buffer)
            if (count == -1) break
            sha256.update(buffer, 0, count)
        }
    }
    val digest = sha256.digest().joinToString("") { "%02x".format(it) }
    val signature = keystore.sign(digest.toByteArray(Charsets.UTF_8)) ?: throw IOException("Capture signing failed.")
    val reservation = JsonObject().apply {
        addProperty("owner_client_id", assignment.ownerClientId)
        addProperty("assignment_id", assignment.assignmentId)
        addProperty("generation", assignment.generation)
        addProperty("document_instance_id", capture.documentId)
        addProperty("field_id", capture.target.fieldId)
        addProperty("slot_id", capture.target.slotId)
        add("repeat_item_id", capture.target.repeatItemId?.let { com.google.gson.JsonPrimitive(it) } ?: JsonNull.INSTANCE)
        addProperty("client_capture_id", capture.id)
        addProperty("upload_key", UUID.randomUUID().toString())
        addProperty("digest", digest)
        addProperty("byte_length", length)
    }
    dao.insertPendingCapture(
        InspectionPendingCapture(
            capture.id, TENANT, VENDOR, assignment.visitId, capture.file.absolutePath,
            reservation.toString(), keyId, signature
        )
    )
}

private fun stagingConnectionMessage(error: IOException): String = when (error) {
    is UnknownHostException -> "The phone could not resolve the staging hostname (DNS)."
    is SSLException -> "The secure connection to staging failed (TLS)."
    is SocketTimeoutException -> "Staging did not respond in time. A request may still have reached the server."
    is ConnectException -> "The phone could not connect to staging."
    else -> "The staging connection ended before the request completed."
}

private suspend fun enrollStagingKey(
    context: Context,
    api: InspectionVisitApi,
    keystore: KeystoreManager,
    deviceId: String,
    proof: String
): Boolean = withContext(Dispatchers.IO) {
    keystore.generateKeyPairIfNeeded()
    val pem = keystore.getPublicKeyPem() ?: return@withContext false
    val fingerprint = keystore.getPublicKeyFingerprint() ?: return@withContext false
    val signature = keystore.sign(proof.toByteArray(Charsets.UTF_8)) ?: return@withContext false
    val response = api.enrollDevice(InspectionDeviceEnrollmentDto(deviceId, proof, pem, signature))
    val result = response.body() ?: return@withContext false
    if (!response.isSuccessful || result.keyFingerprint != fingerprint ||
        runCatching { UUID.fromString(result.keyId) }.isFailure
    ) return@withContext false
    context.getSharedPreferences("gate1_staging_enrollment", Context.MODE_PRIVATE).edit()
        .putString("tenant_id", TENANT)
        .putString("vendor_id", VENDOR)
        .putString("device_id", deviceId)
        .putString("key_id", result.keyId)
        .putString("key_fingerprint", fingerprint)
        .commit()
}
