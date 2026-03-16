package com.trustcapture.vendor.ui.settings

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    onLoggedOut: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val pendingUploads by viewModel.pendingUploadCount.collectAsState()
    var showLogoutDialog by remember { mutableStateOf(false) }
    var showDeleteDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
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
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Account section
            SettingsSection(title = "Account") {
                SettingsInfoRow(Icons.Default.Badge, "Vendor ID", uiState.vendorId)
                SettingsInfoRow(Icons.Default.Phone, "Phone", uiState.phoneNumber)
                SettingsInfoRow(Icons.Default.Fingerprint, "Device ID", uiState.deviceId.take(12) + "...")
                SettingsInfoRow(Icons.Default.Key, "Key Fingerprint", uiState.publicKeyFingerprint)
            }

            // Upload queue section
            if (pendingUploads > 0) {
                SettingsSection(title = "Upload Queue") {
                    SettingsInfoRow(Icons.Default.CloudUpload, "Pending", "$pendingUploads photo(s)")
                    SettingsInfoRow(Icons.Default.Storage, "Encrypted Storage", uiState.encryptedPhotosSize)
                }
            }

            // Device security section
            SettingsSection(title = "Device Security") {
                SettingsInfoRow(
                    Icons.Default.PhoneAndroid,
                    "Environment",
                    if (uiState.isEmulator) "Emulator" else "Physical Device"
                )
                SettingsInfoRow(
                    Icons.Default.Security,
                    "Root Status",
                    if (uiState.isRooted) "Rooted ⚠" else "Clean"
                )
                if (uiState.securityFlags.isNotEmpty()) {
                    SettingsInfoRow(
                        Icons.Default.Flag,
                        "Flags",
                        uiState.securityFlags.joinToString(", ")
                    )
                }
            }

            // Actions section
            SettingsSection(title = "Actions") {
                // Clear cache
                OutlinedButton(
                    onClick = viewModel::clearCache,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.DeleteSweep, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(if (uiState.cacheCleared) "Cache Cleared ✓" else "Clear Cache")
                }

                Spacer(modifier = Modifier.height(8.dp))

                // Logout
                Button(
                    onClick = { showLogoutDialog = true },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error
                    )
                ) {
                    Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Logout")
                }
            }

            // GDPR / Privacy section (Req 24.1-24.7)
            SettingsSection(title = "Privacy & Data (GDPR)") {
                // Privacy mode toggle
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.PrivacyTip, contentDescription = null, modifier = Modifier.size(20.dp))
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text("Privacy Mode", style = MaterialTheme.typography.bodyMedium)
                            Text(
                                "Anonymize vendor ID in exports",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                    Switch(
                        checked = uiState.privacyModeEnabled,
                        onCheckedChange = { viewModel.togglePrivacyMode() }
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                // Export data
                OutlinedButton(
                    onClick = viewModel::exportData,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !uiState.isExporting
                ) {
                    if (uiState.isExporting) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Default.Download, contentDescription = null, modifier = Modifier.size(18.dp))
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Export My Data (JSON)")
                }
                if (uiState.exportPath != null) {
                    Text(
                        "Exported to: ${uiState.exportPath}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                // Delete all data
                Button(
                    onClick = { showDeleteDialog = true },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error
                    ),
                    enabled = !uiState.isDeleting
                ) {
                    Icon(Icons.Default.DeleteForever, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Delete All My Data")
                }
            }

            // About section
            SettingsSection(title = "About") {
                SettingsInfoRow(Icons.Default.Info, "App Version", uiState.appVersion)
                SettingsInfoRow(Icons.Default.Shield, "Encryption", "AES-256-GCM + SQLCipher")
                SettingsInfoRow(Icons.Default.VerifiedUser, "Signing", "ECDSA P-256 (Keystore)")
            }

            Spacer(modifier = Modifier.height(32.dp))
        }
    }

    // Logout confirmation dialog
    if (showLogoutDialog) {
        AlertDialog(
            onDismissRequest = { showLogoutDialog = false },
            title = { Text("Logout") },
            text = {
                if (pendingUploads > 0) {
                    Text("You have $pendingUploads pending upload(s). They will be lost if you logout. Continue?")
                } else {
                    Text("Are you sure you want to logout?")
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    showLogoutDialog = false
                    viewModel.logout(onLoggedOut)
                }) { Text("Logout", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutDialog = false }) { Text("Cancel") }
            }
        )
    }

    // GDPR delete confirmation dialog
    if (showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteDialog = false },
            title = { Text("Delete All Data") },
            text = {
                Text("This will permanently delete all your photos, audit logs, and preferences. You will be logged out. This action cannot be undone.")
            },
            confirmButton = {
                TextButton(onClick = {
                    showDeleteDialog = false
                    viewModel.deleteAllData(onLoggedOut)
                }) { Text("Delete Everything", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteDialog = false }) { Text("Cancel") }
            }
        )
    }
}

@Composable
private fun SettingsSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(12.dp))
            content()
        }
    }
}

@Composable
private fun SettingsInfoRow(icon: ImageVector, label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            icon,
            contentDescription = null,
            modifier = Modifier.size(20.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.width(12.dp))
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(100.dp)
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium
        )
    }
}
