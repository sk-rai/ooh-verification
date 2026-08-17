package com.trustcapture.vendor.ui.home

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import com.trustcapture.vendor.service.TrackingService

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onCampaigns: () -> Unit,
    onQuickCapture: () -> Unit,
    onSettings: () -> Unit,
    onLoggedOut: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    // --- Background Location Permission Handling (Task A2) ---

    // Step 1: Fine location permission launcher (needed before background on Android 10+)
    var fineLocationGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) ==
                    PackageManager.PERMISSION_GRANTED
        )
    }

    // Step 2: Background location launcher
    val backgroundLocationLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        viewModel.onBackgroundLocationPermissionResult(granted)
        if (granted) {
            TrackingService.startService(context)
        }
    }

    // Step 1 launcher: request fine location first, then background
    val fineLocationLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        fineLocationGranted = granted
        if (granted && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Now request background location
            backgroundLocationLauncher.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
        } else if (granted) {
            // Pre-Android 10: fine location is sufficient for background
            viewModel.onBackgroundLocationPermissionResult(true)
            TrackingService.startService(context)
        } else {
            viewModel.onBackgroundLocationPermissionResult(false)
        }
    }

    // Start tracking service if permission was already granted and tracking enabled
    LaunchedEffect(uiState.trackingEnabled, uiState.backgroundLocationGranted) {
        if (uiState.trackingEnabled && uiState.backgroundLocationGranted) {
            TrackingService.startService(context)
        }
    }

    // Also auto-start if permission was previously granted (returning user)
    LaunchedEffect(uiState.trackingEnabled) {
        if (uiState.trackingEnabled) {
            val hasFine = ContextCompat.checkSelfPermission(
                context, Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED
            val hasBackground = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ContextCompat.checkSelfPermission(
                    context, Manifest.permission.ACCESS_BACKGROUND_LOCATION
                ) == PackageManager.PERMISSION_GRANTED
            } else {
                hasFine
            }
            if (hasFine && hasBackground) {
                TrackingService.startService(context)
            }
        }
    }

    // Background Location Rationale Dialog (Task A2)
    if (uiState.showBackgroundLocationDialog) {
        AlertDialog(
            onDismissRequest = { viewModel.dismissBackgroundLocationDialog() },
            icon = { Icon(Icons.Default.LocationOn, contentDescription = null) },
            title = { Text("Background Location Access") },
            text = {
                Text(
                    "TrustCapture collects location periodically to verify field attendance. " +
                            "This helps ensure accurate tracking of your work locations.\n\n" +
                            "You can disable this anytime from Settings.",
                    style = MaterialTheme.typography.bodyMedium
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        if (!fineLocationGranted) {
                            // Request fine location first
                            fineLocationLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                            // Already have fine, request background
                            backgroundLocationLauncher.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                        } else {
                            // Pre-Q: fine is enough
                            viewModel.onBackgroundLocationPermissionResult(true)
                            TrackingService.startService(context)
                        }
                    }
                ) {
                    Text("Allow")
                }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.dismissBackgroundLocationDialog() }) {
                    Text("Not Now")
                }
            }
        )
    }

    // Maintenance mode — show full-screen message
    if (uiState.maintenanceEnabled) {
        Scaffold { padding ->
            Column(
                modifier = Modifier.fillMaxSize().padding(padding).padding(32.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Icon(Icons.Default.Build, contentDescription = null, modifier = Modifier.size(64.dp), tint = MaterialTheme.colorScheme.primary)
                Spacer(modifier = Modifier.height(16.dp))
                Text("Under Maintenance", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.Center)
                if (uiState.maintenanceMessage.isNotBlank()) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(uiState.maintenanceMessage, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(modifier = Modifier.height(24.dp))
                OutlinedButton(onClick = { viewModel.logout(onLoggedOut) }) { Text("Sign Out") }
            }
        }
        return
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(uiState.tenantName) },
                actions = {
                    if (uiState.showSettings) {
                        IconButton(onClick = onSettings) {
                            Icon(Icons.Default.Settings, contentDescription = "Settings")
                        }
                    }
                    IconButton(onClick = { viewModel.logout(onLoggedOut) }) {
                        Icon(Icons.Default.Logout, contentDescription = "Logout")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Icon(
                Icons.Default.Verified,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                "What would you like to do?",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(32.dp))

            // My Campaigns button (shown if feature enabled AND vendor has campaigns)
            if (uiState.showCampaigns && uiState.hasCampaigns) {
                ElevatedCard(
                    onClick = onCampaigns,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(20.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Campaign,
                            contentDescription = null,
                            modifier = Modifier.size(40.dp),
                            tint = MaterialTheme.colorScheme.primary
                        )
                        Spacer(modifier = Modifier.width(16.dp))
                        Column {
                            Text(
                                "My Campaigns",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                "Capture for assigned campaign locations",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            // Quick Capture button (shown if feature enabled)
            if (uiState.quickCaptureEnabled) {
                ElevatedCard(
                    onClick = onQuickCapture,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(20.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.FlashOn,
                            contentDescription = null,
                            modifier = Modifier.size(40.dp),
                            tint = MaterialTheme.colorScheme.secondary
                        )
                        Spacer(modifier = Modifier.width(16.dp))
                        Column {
                            Text(
                                "Quick Capture",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                "Capture evidence without a campaign",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }

            // Pending uploads indicator
            if (uiState.pendingUploads > 0) {
                Spacer(modifier = Modifier.height(24.dp))
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer
                    )
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.CloudUpload,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSecondaryContainer
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            "${uiState.pendingUploads} upload(s) pending",
                            color = MaterialTheme.colorScheme.onSecondaryContainer
                        )
                    }
                }
            }
        }
    }
}
