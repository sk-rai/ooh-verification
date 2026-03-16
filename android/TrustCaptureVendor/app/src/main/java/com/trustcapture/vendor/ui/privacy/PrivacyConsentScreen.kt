package com.trustcapture.vendor.ui.privacy

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.PrivacyTip
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PrivacyConsentScreen(
    onConsentGiven: () -> Unit,
    viewModel: PrivacyConsentViewModel = hiltViewModel()
) {
    var locationConsent by remember { mutableStateOf(false) }
    val isSaving by viewModel.isSaving.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Privacy & Data Collection") })
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            // App icon / branding
            Icon(
                Icons.Default.PrivacyTip,
                contentDescription = null,
                modifier = Modifier.size(48.dp).align(Alignment.CenterHorizontally),
                tint = MaterialTheme.colorScheme.primary
            )

            Text(
                text = "TrustCapture™ Privacy Policy",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold
            )

            // Privacy policy summary
            ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        "What data we collect",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "• GPS location when capturing photos\n" +
                        "• WiFi network information for location verification\n" +
                        "• Cell tower data for location triangulation\n" +
                        "• Environmental sensor readings (pressure, light)\n" +
                        "• Device security status (emulator/root detection)\n" +
                        "• Photos you capture through the app",
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        "How we use your data",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "• Verify photo authenticity and location\n" +
                        "• Prevent fraud through multi-sensor triangulation\n" +
                        "• Generate tamper-proof audit trails\n" +
                        "• Comply with industry regulations (HIPAA, etc.)",
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        "Your rights (GDPR)",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "• Export your data in JSON format\n" +
                        "• Request deletion of your data\n" +
                        "• Enable privacy mode to anonymize your ID\n" +
                        "• Withdraw consent at any time in Settings",
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Location consent checkbox
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Checkbox(
                    checked = locationConsent,
                    onCheckedChange = { locationConsent = it }
                )
                Spacer(modifier = Modifier.width(8.dp))
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.LocationOn, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Location Data Collection", fontWeight = FontWeight.Medium)
                    }
                    Text(
                        "I consent to collection of GPS, WiFi, and cell tower data for photo verification.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Accept button
            Button(
                onClick = {
                    viewModel.saveConsent(locationConsent, onConsentGiven)
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = locationConsent && !isSaving
            ) {
                if (isSaving) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                } else {
                    Text("Accept & Continue")
                }
            }

            Text(
                "By continuing, you agree to our Privacy Policy and Terms of Service.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}
