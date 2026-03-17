package com.trustcapture.vendor.ui.camera

import android.Manifest
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import java.io.File
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CameraScreen(
    onBack: () -> Unit,
    viewModel: CameraViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    // Permission state tracking
    var hasCameraPermission by remember { mutableStateOf(false) }
    var hasLocationPermission by remember { mutableStateOf(false) }
    var permissionsRequested by remember { mutableStateOf(false) }
    var showRationaleDialog by remember { mutableStateOf(false) }
    var permanentlyDenied by remember { mutableStateOf(false) }
    var previouslyDeniedCamera by remember { mutableStateOf(false) }
    var previouslyDeniedLocation by remember { mutableStateOf(false) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val cameraGranted = permissions[Manifest.permission.CAMERA] == true
        val locationGranted = permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true
        hasCameraPermission = cameraGranted
        hasLocationPermission = locationGranted
        permissionsRequested = true

        if (!cameraGranted && previouslyDeniedCamera) permanentlyDenied = true
        if (!locationGranted && previouslyDeniedLocation) permanentlyDenied = true
        if (!cameraGranted) previouslyDeniedCamera = true
        if (!locationGranted) previouslyDeniedLocation = true
    }

    // Show rationale first, then request permissions
    LaunchedEffect(Unit) {
        showRationaleDialog = true
    }

    // Permission rationale dialog (Task 35.2)
    if (showRationaleDialog && !permissionsRequested) {
        AlertDialog(
            onDismissRequest = { /* don't dismiss */ },
            icon = { Icon(Icons.Default.Security, contentDescription = null) },
            title = { Text("Permissions Required") },
            text = {
                Text(
                    "TrustCapture needs:\n\n" +
                    "\u2022 Camera \u2014 to capture verified photos of campaign locations\n" +
                    "\u2022 Location \u2014 to geo-tag photos and verify you're at the correct site\n\n" +
                    "These are essential for photo verification and fraud prevention."
                )
            },
            confirmButton = {
                Button(onClick = {
                    showRationaleDialog = false
                    permissionLauncher.launch(
                        arrayOf(Manifest.permission.CAMERA, Manifest.permission.ACCESS_FINE_LOCATION)
                    )
                }) { Text("Grant Permissions") }
            },
            dismissButton = {
                TextButton(onClick = {
                    showRationaleDialog = false
                    permissionsRequested = true
                }) { Text("Not Now") }
            }
        )
    }

    // "Permanently denied" dialog — direct to Settings (Task 35.3)
    if (permanentlyDenied) {
        AlertDialog(
            onDismissRequest = { permanentlyDenied = false },
            icon = { Icon(Icons.Default.Settings, contentDescription = null) },
            title = { Text("Permissions Blocked") },
            text = {
                Text(
                    "Camera and location permissions have been permanently denied. " +
                    "Please open Settings and enable them manually for TrustCapture to work."
                )
            },
            confirmButton = {
                Button(onClick = {
                    permanentlyDenied = false
                    context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                        data = Uri.fromParts("package", context.packageName, null)
                    })
                }) { Text("Open Settings") }
            },
            dismissButton = {
                TextButton(onClick = { permanentlyDenied = false }) { Text("Cancel") }
            }
        )
    }

    // Collect GPS location updates with adaptive power management
    LaunchedEffect(hasLocationPermission) {
        if (hasLocationPermission) {
            com.trustcapture.vendor.util.LocationHelper.locationUpdates(
                context = context,
                initialMode = com.trustcapture.vendor.util.GpsPowerMode.BALANCED
            ).collect { loc ->
                viewModel.onLocationUpdated(loc.latitude, loc.longitude, loc.accuracy)
            }
        }
    }

    when (uiState.screenState) {
        CameraScreenState.PREVIEW -> {
            if (uiState.captureBlocked) {
                CaptureBlockedContent(
                    reason = uiState.captureBlockedReason ?: "Device security not supported",
                    onBack = onBack
                )
            } else if (hasCameraPermission) {
                CameraPreviewContent(
                    gpsStatus = uiState.gpsStatus,
                    gpsWarning = uiState.gpsWarning,
                    sensorSummary = uiState.sensorSummary,
                    wifiCount = uiState.wifiCount,
                    cellTowerCount = uiState.cellTowerCount,
                    isEmulator = uiState.isEmulator,
                    isRooted = uiState.isRooted,
                    onPhotoCaptured = { uri -> viewModel.onPhotoCaptured(uri) },
                    onBack = onBack
                )
            } else {
                PermissionDeniedContent(
                    onBack = onBack,
                    onRetryPermissions = {
                        showRationaleDialog = true
                        permissionsRequested = false
                    },
                    onOpenSettings = {
                        context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                            data = Uri.fromParts("package", context.packageName, null)
                        })
                    }
                )
            }
        }
        CameraScreenState.PROCESSING -> {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator()
                    Spacer(modifier = Modifier.height(16.dp))
                    Text("Applying watermark...", style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        CameraScreenState.CAPTURED, CameraScreenState.UPLOADING -> {
            PhotoReviewContent(
                uiState = uiState,
                onRetake = viewModel::retakePhoto,
                onUpload = viewModel::uploadPhoto,
                onBack = onBack,
                onAddSafetyTag = viewModel::addSafetyTag,
                onRemoveSafetyTag = viewModel::removeSafetyTag,
                onRoomLabelChanged = viewModel::setRoomLabel,
                onCaptureAnother = viewModel::captureAnother
            )
        }
    }
}

@Composable
private fun CameraPreviewContent(
    gpsStatus: String,
    gpsWarning: String?,
    sensorSummary: String,
    wifiCount: Int,
    cellTowerCount: Int,
    isEmulator: Boolean,
    isRooted: Boolean,
    onPhotoCaptured: (Uri) -> Unit,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val imageCapture = remember {
        ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .build()
    }

    Box(modifier = Modifier.fillMaxSize()) {
        AndroidView(
            factory = { ctx ->
                PreviewView(ctx).also { previewView ->
                    val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                    cameraProviderFuture.addListener({
                        val cameraProvider = cameraProviderFuture.get()
                        val preview = Preview.Builder().build().also {
                            it.surfaceProvider = previewView.surfaceProvider
                        }
                        try {
                            cameraProvider.unbindAll()
                            cameraProvider.bindToLifecycle(
                                lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, imageCapture
                            )
                        } catch (_: Exception) { }
                    }, ContextCompat.getMainExecutor(ctx))
                }
            },
            modifier = Modifier.fillMaxSize()
        )

        // Top bar overlay
        Row(
            modifier = Modifier.fillMaxWidth().statusBarsPadding().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                IconButton(
                    onClick = onBack,
                    colors = IconButtonDefaults.iconButtonColors(
                        containerColor = Color.Black.copy(alpha = 0.5f), contentColor = Color.White
                    )
                ) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") }
                if (isEmulator) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Surface(color = Color(0xFFFF6D00).copy(alpha = 0.85f), shape = MaterialTheme.shapes.small) {
                        Row(modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.PhoneAndroid, contentDescription = null, tint = Color.White, modifier = Modifier.size(14.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("EMULATOR MODE", color = Color.White, style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
                if (isRooted) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Surface(color = Color.Red.copy(alpha = 0.85f), shape = MaterialTheme.shapes.small) {
                        Row(modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = Color.White, modifier = Modifier.size(14.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("ROOTED DEVICE", color = Color.White, style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                StatusChip(Icons.Default.LocationOn, Color.Green, gpsStatus)
                Spacer(modifier = Modifier.height(4.dp))
                StatusChip(Icons.Default.Sensors, Color.Cyan, sensorSummary)
                Spacer(modifier = Modifier.height(4.dp))
                StatusChip(Icons.Default.Wifi, if (wifiCount > 0) Color.Green else Color.Yellow, if (wifiCount > 0) "$wifiCount networks" else "No WiFi")
                Spacer(modifier = Modifier.height(4.dp))
                StatusChip(Icons.Default.CellTower, if (cellTowerCount > 0) Color.Green else Color.Yellow, if (cellTowerCount > 0) "$cellTowerCount towers" else "No cell")
            }
        }

        // GPS accuracy warning banner
        if (gpsWarning != null) {
            Surface(
                modifier = Modifier.fillMaxWidth().align(Alignment.BottomCenter).padding(bottom = 120.dp).padding(horizontal = 32.dp),
                color = Color(0xFFFF6D00).copy(alpha = 0.9f), shape = MaterialTheme.shapes.small
            ) {
                Row(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
                    Icon(Icons.Default.Warning, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(gpsWarning, color = Color.White, style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        // Capture button
        Box(modifier = Modifier.fillMaxWidth().align(Alignment.BottomCenter).padding(bottom = 48.dp), contentAlignment = Alignment.Center) {
            IconButton(
                onClick = { capturePhoto(context, imageCapture, onPhotoCaptured) },
                modifier = Modifier.size(72.dp),
                colors = IconButtonDefaults.iconButtonColors(containerColor = Color.White, contentColor = Color.Black)
            ) { Icon(Icons.Default.CameraAlt, contentDescription = "Capture Photo", modifier = Modifier.size(36.dp)) }
        }
    }
}

@Composable
private fun StatusChip(icon: androidx.compose.ui.graphics.vector.ImageVector, tint: Color, text: String) {
    Surface(color = Color.Black.copy(alpha = 0.6f), shape = MaterialTheme.shapes.small) {
        Row(modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(16.dp))
            Spacer(modifier = Modifier.width(4.dp))
            Text(text = text, color = Color.White, style = MaterialTheme.typography.bodySmall)
        }
    }
}

private fun capturePhoto(context: Context, imageCapture: ImageCapture, onCaptured: (Uri) -> Unit) {
    val photoFile = File(context.cacheDir, "TC_${SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())}.jpg")
    val outputOptions = ImageCapture.OutputFileOptions.Builder(photoFile).build()
    imageCapture.takePicture(
        outputOptions, ContextCompat.getMainExecutor(context),
        object : ImageCapture.OnImageSavedCallback {
            override fun onImageSaved(output: ImageCapture.OutputFileResults) { onCaptured(Uri.fromFile(photoFile)) }
            override fun onError(exception: ImageCaptureException) { /* Handle error */ }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PhotoReviewContent(
    uiState: CameraUiState,
    onRetake: () -> Unit,
    onUpload: () -> Unit,
    onBack: () -> Unit,
    onAddSafetyTag: (String) -> Unit = {},
    onRemoveSafetyTag: (String) -> Unit = {},
    onRoomLabelChanged: (String) -> Unit = {},
    onCaptureAnother: () -> Unit = {}
) {
    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(message = it, duration = SnackbarDuration.Long) }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Review Photo") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") } }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp).verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Photo preview
            Card(modifier = Modifier.fillMaxWidth().heightIn(min = 200.dp, max = 300.dp)) {
                val displayUri = uiState.watermarkedPhotoUri ?: uiState.originalPhotoUri
                if (displayUri != null) {
                    AsyncImage(model = displayUri, contentDescription = "Captured photo with watermark", modifier = Modifier.fillMaxSize())
                }
            }
            Spacer(modifier = Modifier.height(16.dp))

            // Metadata card
            ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Capture Details", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    Spacer(modifier = Modifier.height(8.dp))
                    if (uiState.latitude != null && uiState.longitude != null) {
                        MetadataRow(Icons.Default.LocationOn, "GPS", "%.7f, %.7f".format(uiState.latitude, uiState.longitude))
                        if (uiState.accuracy != null) MetadataRow(Icons.Default.GpsFixed, "Accuracy", "\u00b1${uiState.accuracy!!.toInt()} meters")
                    } else {
                        MetadataRow(Icons.Default.LocationOff, "GPS", "Not available")
                    }
                    MetadataRow(Icons.Default.Schedule, "Time", SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date()))
                    MetadataRow(
                        if (uiState.signatureJson != null) Icons.Default.VerifiedUser else Icons.Default.Warning,
                        "Signed", if (uiState.signatureJson != null) "ECDSA-SHA256 \u2713" else "Not signed"
                    )
                    uiState.pressureHpa?.let { MetadataRow(Icons.Default.Speed, "Pressure", "%.1f hPa".format(it)) }
                    uiState.lightLux?.let { MetadataRow(Icons.Default.LightMode, "Light", "${it.toInt()} lux") }
                    uiState.magneticMagnitude?.let { MetadataRow(Icons.Default.Explore, "Magnetic", "%.1f \u00b5T".format(it)) }
                    MetadataRow(Icons.Default.Wifi, "WiFi", if (uiState.wifiCount > 0) "${uiState.wifiCount} networks" else "N/A")
                    MetadataRow(Icons.Default.CellTower, "Cell", if (uiState.cellTowerCount > 0) "${uiState.cellTowerCount} towers" else "N/A")
                    if (uiState.tremorDetected) MetadataRow(Icons.Default.Warning, "Tremor", "Detected \u26a0")
                    if (uiState.confidenceScore != null) {
                        Spacer(modifier = Modifier.height(4.dp))
                        MetadataRow(Icons.Default.Security, "Confidence", "${uiState.confidenceScore}/100")
                        if (uiState.triangulationFlags.isNotEmpty()) MetadataRow(Icons.Default.Flag, "Flags", uiState.triangulationFlags.joinToString(", "))
                    }
                    if (uiState.isEmulator || uiState.isRooted) {
                        Spacer(modifier = Modifier.height(4.dp))
                        if (uiState.isEmulator) MetadataRow(Icons.Default.PhoneAndroid, "Device", "Emulator \u26a0")
                        if (uiState.isRooted) MetadataRow(Icons.Default.Warning, "Root", "Detected \u26a0")
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))

            // Campaign-type-specific UI sections
            val config = uiState.campaignConfig

            // Insurance: photo sequence counter (Req 18.2)
            if (config.allowMultiPhoto) {
                Surface(color = MaterialTheme.colorScheme.tertiaryContainer, shape = MaterialTheme.shapes.small, modifier = Modifier.fillMaxWidth()) {
                    Row(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Collections, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Photo ${uiState.photoSequenceNumber} of claim", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
            }

            // Healthcare: HIPAA compliance badge (Req 18.4)
            if (config.enforceHipaa) {
                Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.small, modifier = Modifier.fillMaxWidth()) {
                    Row(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.HealthAndSafety, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("HIPAA-compliant \u00b7 AES-256-GCM encrypted", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
            }

            // Construction: safety compliance tags (Req 18.1)
            if (config.requiresSafetyTags) {
                var tagInput by remember { mutableStateOf("") }
                OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("Safety Compliance Tags", style = MaterialTheme.typography.labelMedium)
                        Spacer(modifier = Modifier.height(4.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(value = tagInput, onValueChange = { tagInput = it }, modifier = Modifier.weight(1f), placeholder = { Text("e.g. PPE, Harness") }, singleLine = true, textStyle = MaterialTheme.typography.bodySmall)
                            Spacer(modifier = Modifier.width(8.dp))
                            FilledTonalButton(onClick = { onAddSafetyTag(tagInput); tagInput = "" }, enabled = tagInput.isNotBlank()) { Text("Add") }
                        }
                        if (uiState.safetyTags.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(6.dp))
                            LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                items(uiState.safetyTags) { tag ->
                                    InputChip(selected = true, onClick = { onRemoveSafetyTag(tag) }, label = { Text(tag, style = MaterialTheme.typography.bodySmall) },
                                        trailingIcon = { Icon(Icons.Default.Close, contentDescription = "Remove", modifier = Modifier.size(14.dp)) })
                                }
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
            }

            // Property management: room label (Req 18.5)
            if (config.roomOrganization) {
                OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("Room Label", style = MaterialTheme.typography.labelMedium)
                        Spacer(modifier = Modifier.height(4.dp))
                        OutlinedTextField(value = uiState.roomLabel, onValueChange = onRoomLabelChanged, modifier = Modifier.fillMaxWidth(), placeholder = { Text("e.g. Kitchen, Bedroom 1, Bathroom") }, singleLine = true, textStyle = MaterialTheme.typography.bodySmall)
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
            }

            // Upload success message
            if (uiState.uploadSuccess) {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer), modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Default.CheckCircle, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(8.dp))
                        Text("Photo uploaded successfully", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                        Text("Campaign: ${uiState.campaignCode}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            // Error message
            if (uiState.error != null) {
                Text(text = uiState.error!!, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                Spacer(modifier = Modifier.height(8.dp))
            }

            // Action buttons
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (uiState.uploadSuccess) {
                    OutlinedButton(onClick = onBack, modifier = Modifier.weight(1f).height(48.dp)) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp)); Text("Campaigns")
                    }
                    Button(onClick = if (uiState.campaignConfig.allowMultiPhoto) onCaptureAnother else onRetake, modifier = Modifier.weight(1f).height(48.dp)) {
                        Icon(Icons.Default.CameraAlt, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp)); Text(if (uiState.campaignConfig.allowMultiPhoto) "Next Photo" else "Capture Another")
                    }
                } else {
                    OutlinedButton(onClick = onRetake, modifier = Modifier.weight(1f).height(48.dp), enabled = !uiState.isUploading) {
                        Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp)); Text("Retake")
                    }
                    Button(onClick = onUpload, modifier = Modifier.weight(1f).height(48.dp), enabled = !uiState.isUploading) {
                        if (uiState.isUploading) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                            Spacer(modifier = Modifier.width(8.dp)); Text("Uploading...")
                        } else {
                            Icon(Icons.Default.CloudUpload, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(4.dp)); Text("Upload")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MetadataRow(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(16.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(modifier = Modifier.width(8.dp))
        Text("$label: ", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun CaptureBlockedContent(reason: String, onBack: () -> Unit) {
    Column(modifier = Modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(80.dp), tint = MaterialTheme.colorScheme.error)
        Spacer(modifier = Modifier.height(16.dp))
        Text("Capture Unavailable", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
        Spacer(modifier = Modifier.height(8.dp))
        Text(reason, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(modifier = Modifier.height(24.dp))
        Button(onClick = onBack) { Text("Go Back") }
    }
}

@Composable
private fun PermissionDeniedContent(onBack: () -> Unit, onRetryPermissions: () -> Unit = {}, onOpenSettings: () -> Unit = {}) {
    Column(modifier = Modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Icon(Icons.Default.CameraAlt, contentDescription = null, modifier = Modifier.size(80.dp), tint = MaterialTheme.colorScheme.error)
        Spacer(modifier = Modifier.height(16.dp))
        Text("Camera Permission Required", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
        Spacer(modifier = Modifier.height(8.dp))
        Text("TrustCapture needs camera and location access to capture verified photos. Without these permissions, photo capture cannot work.",
            style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(modifier = Modifier.height(24.dp))
        Button(onClick = onRetryPermissions, modifier = Modifier.fillMaxWidth(0.7f)) {
            Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(modifier = Modifier.width(8.dp)); Text("Grant Permissions")
        }
        Spacer(modifier = Modifier.height(8.dp))
        OutlinedButton(onClick = onOpenSettings, modifier = Modifier.fillMaxWidth(0.7f)) {
            Icon(Icons.Default.Settings, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(modifier = Modifier.width(8.dp)); Text("Open Settings")
        }
        Spacer(modifier = Modifier.height(8.dp))
        TextButton(onClick = onBack) { Text("Go Back") }
    }
}
