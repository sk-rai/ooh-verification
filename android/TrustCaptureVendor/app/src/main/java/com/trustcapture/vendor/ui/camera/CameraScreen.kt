package com.trustcapture.vendor.ui.camera

import android.Manifest
import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
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

    // Permission handling
    var hasCameraPermission by remember { mutableStateOf(false) }
    var hasLocationPermission by remember { mutableStateOf(false) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        hasCameraPermission = permissions[Manifest.permission.CAMERA] == true
        hasLocationPermission = permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true
    }

    LaunchedEffect(Unit) {
        permissionLauncher.launch(
            arrayOf(
                Manifest.permission.CAMERA,
                Manifest.permission.ACCESS_FINE_LOCATION
            )
        )
    }

    // Collect GPS location updates
    LaunchedEffect(hasLocationPermission) {
        if (hasLocationPermission) {
            com.trustcapture.vendor.util.locationUpdates(context).collect { loc ->
                viewModel.onLocationUpdated(loc.latitude, loc.longitude, loc.accuracy)
            }
        }
    }

    when (uiState.screenState) {
        CameraScreenState.PREVIEW -> {
            if (hasCameraPermission) {
                CameraPreviewContent(
                    gpsStatus = uiState.gpsStatus,
                    sensorSummary = uiState.sensorSummary,
                    wifiCount = uiState.wifiCount,
                    cellTowerCount = uiState.cellTowerCount,
                    onPhotoCaptured = { uri ->
                        viewModel.onPhotoCaptured(uri)
                    },
                    onBack = onBack
                )
            } else {
                PermissionDeniedContent(onBack = onBack)
            }
        }
        CameraScreenState.PROCESSING -> {
            // Show a loading indicator while watermark is being applied
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
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
                onBack = onBack
            )
        }
    }
}

@Composable
private fun CameraPreviewContent(
    gpsStatus: String,
    sensorSummary: String,
    wifiCount: Int,
    cellTowerCount: Int,
    onPhotoCaptured: (Uri) -> Unit,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val imageCapture = remember { ImageCapture.Builder().build() }

    Box(modifier = Modifier.fillMaxSize()) {
        // Camera preview
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
                                lifecycleOwner,
                                CameraSelector.DEFAULT_BACK_CAMERA,
                                preview,
                                imageCapture
                            )
                        } catch (e: Exception) {
                            // Camera bind failed
                        }
                    }, ContextCompat.getMainExecutor(ctx))
                }
            },
            modifier = Modifier.fillMaxSize()
        )

        // Top bar overlay
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(
                onClick = onBack,
                colors = IconButtonDefaults.iconButtonColors(
                    containerColor = Color.Black.copy(alpha = 0.5f),
                    contentColor = Color.White
                )
            ) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
            }

            Column(horizontalAlignment = Alignment.End) {
                // GPS status chip
                Surface(
                    color = Color.Black.copy(alpha = 0.6f),
                    shape = MaterialTheme.shapes.small
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.LocationOn,
                            contentDescription = null,
                            tint = Color.Green,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = gpsStatus,
                            color = Color.White,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
                Spacer(modifier = Modifier.height(4.dp))
                // Sensor status chip
                Surface(
                    color = Color.Black.copy(alpha = 0.6f),
                    shape = MaterialTheme.shapes.small
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Sensors,
                            contentDescription = null,
                            tint = Color.Cyan,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = sensorSummary,
                            color = Color.White,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
                Spacer(modifier = Modifier.height(4.dp))
                // WiFi status chip
                Surface(
                    color = Color.Black.copy(alpha = 0.6f),
                    shape = MaterialTheme.shapes.small
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Wifi,
                            contentDescription = null,
                            tint = if (wifiCount > 0) Color.Green else Color.Yellow,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = if (wifiCount > 0) "$wifiCount networks" else "No WiFi",
                            color = Color.White,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
                Spacer(modifier = Modifier.height(4.dp))
                // Cell tower status chip
                Surface(
                    color = Color.Black.copy(alpha = 0.6f),
                    shape = MaterialTheme.shapes.small
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.CellTower,
                            contentDescription = null,
                            tint = if (cellTowerCount > 0) Color.Green else Color.Yellow,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = if (cellTowerCount > 0) "$cellTowerCount towers" else "No cell",
                            color = Color.White,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
        }

        // Capture button at bottom
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .align(Alignment.BottomCenter)
                .padding(bottom = 48.dp),
            contentAlignment = Alignment.Center
        ) {
            IconButton(
                onClick = {
                    capturePhoto(context, imageCapture, onPhotoCaptured)
                },
                modifier = Modifier.size(72.dp),
                colors = IconButtonDefaults.iconButtonColors(
                    containerColor = Color.White,
                    contentColor = Color.Black
                )
            ) {
                Icon(
                    Icons.Default.CameraAlt,
                    contentDescription = "Capture Photo",
                    modifier = Modifier.size(36.dp)
                )
            }
        }
    }
}

private fun capturePhoto(
    context: Context,
    imageCapture: ImageCapture,
    onCaptured: (Uri) -> Unit
) {
    val photoFile = File(
        context.cacheDir,
        "TC_${SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())}.jpg"
    )
    val outputOptions = ImageCapture.OutputFileOptions.Builder(photoFile).build()

    imageCapture.takePicture(
        outputOptions,
        ContextCompat.getMainExecutor(context),
        object : ImageCapture.OnImageSavedCallback {
            override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                onCaptured(Uri.fromFile(photoFile))
            }
            override fun onError(exception: ImageCaptureException) {
                // Handle error
            }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PhotoReviewContent(
    uiState: CameraUiState,
    onRetake: () -> Unit,
    onUpload: () -> Unit,
    onBack: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Review Photo") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Photo preview — show watermarked version
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
            ) {
                val displayUri = uiState.watermarkedPhotoUri ?: uiState.originalPhotoUri
                if (displayUri != null) {
                    AsyncImage(
                        model = displayUri,
                        contentDescription = "Captured photo with watermark",
                        modifier = Modifier.fillMaxSize()
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Metadata card
            ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Capture Details",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    if (uiState.latitude != null && uiState.longitude != null) {
                        MetadataRow(
                            icon = Icons.Default.LocationOn,
                            label = "GPS",
                            value = "%.7f, %.7f".format(uiState.latitude, uiState.longitude)
                        )
                        if (uiState.accuracy != null) {
                            MetadataRow(
                                icon = Icons.Default.GpsFixed,
                                label = "Accuracy",
                                value = "±${uiState.accuracy!!.toInt()} meters"
                            )
                        }
                    } else {
                        MetadataRow(
                            icon = Icons.Default.LocationOff,
                            label = "GPS",
                            value = "Not available"
                        )
                    }

                    MetadataRow(
                        icon = Icons.Default.Schedule,
                        label = "Time",
                        value = SimpleDateFormat(
                            "yyyy-MM-dd HH:mm:ss",
                            Locale.getDefault()
                        ).format(Date())
                    )

                    // Signature status
                    MetadataRow(
                        icon = if (uiState.signatureJson != null) Icons.Default.VerifiedUser else Icons.Default.Warning,
                        label = "Signed",
                        value = if (uiState.signatureJson != null) "ECDSA-SHA256 ✓" else "Not signed"
                    )

                    // Environmental sensors
                    if (uiState.pressureHpa != null) {
                        MetadataRow(
                            icon = Icons.Default.Speed,
                            label = "Pressure",
                            value = "%.1f hPa".format(uiState.pressureHpa)
                        )
                    }
                    if (uiState.lightLux != null) {
                        MetadataRow(
                            icon = Icons.Default.LightMode,
                            label = "Light",
                            value = "${uiState.lightLux!!.toInt()} lux"
                        )
                    }
                    if (uiState.magneticMagnitude != null) {
                        MetadataRow(
                            icon = Icons.Default.Explore,
                            label = "Magnetic",
                            value = "%.1f µT".format(uiState.magneticMagnitude)
                        )
                    }
                    MetadataRow(
                        icon = Icons.Default.Wifi,
                        label = "WiFi",
                        value = if (uiState.wifiCount > 0) "${uiState.wifiCount} networks" else "N/A"
                    )
                    MetadataRow(
                        icon = Icons.Default.CellTower,
                        label = "Cell",
                        value = if (uiState.cellTowerCount > 0) "${uiState.cellTowerCount} towers" else "N/A"
                    )
                    if (uiState.tremorDetected) {
                        MetadataRow(
                            icon = Icons.Default.Warning,
                            label = "Tremor",
                            value = "Detected ⚠"
                        )
                    }

                    // Confidence score
                    if (uiState.confidenceScore != null) {
                        Spacer(modifier = Modifier.height(4.dp))
                        MetadataRow(
                            icon = Icons.Default.Security,
                            label = "Confidence",
                            value = "${uiState.confidenceScore}/100"
                        )
                        if (uiState.triangulationFlags.isNotEmpty()) {
                            MetadataRow(
                                icon = Icons.Default.Flag,
                                label = "Flags",
                                value = uiState.triangulationFlags.joinToString(", ")
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Upload success message
            if (uiState.uploadSuccess) {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer
                    ),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Photo uploaded successfully")
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            // Error message
            if (uiState.error != null) {
                Text(
                    text = uiState.error!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
                Spacer(modifier = Modifier.height(8.dp))
            }

            // Action buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = onRetake,
                    modifier = Modifier.weight(1f).height(48.dp),
                    enabled = !uiState.isUploading
                ) {
                    Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Retake")
                }
                Button(
                    onClick = onUpload,
                    modifier = Modifier.weight(1f).height(48.dp),
                    enabled = !uiState.isUploading && !uiState.uploadSuccess
                ) {
                    if (uiState.isUploading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Icon(Icons.Default.CloudUpload, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Upload")
                    }
                }
            }
        }
    }
}

@Composable
private fun MetadataRow(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    value: String
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            icon,
            contentDescription = null,
            modifier = Modifier.size(16.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = "$label: ",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
private fun PermissionDeniedContent(onBack: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.CameraAlt,
            contentDescription = null,
            modifier = Modifier.size(80.dp),
            tint = MaterialTheme.colorScheme.error
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Camera Permission Required",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "TrustCapture needs camera and location access to capture verified photos. Please grant permissions in Settings.",
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.height(24.dp))
        Button(onClick = onBack) {
            Text("Go Back")
        }
    }
}
