package com.trustcapture.vendor

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import com.trustcapture.vendor.data.local.datastore.UserPreferences
import com.trustcapture.vendor.data.remote.dto.AppVersionResponse
import com.trustcapture.vendor.ui.navigation.Routes
import com.trustcapture.vendor.ui.navigation.TrustCaptureNavGraph
import com.trustcapture.vendor.ui.theme.TrustCaptureTheme
import com.trustcapture.vendor.util.UpdateChecker
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.flow.first
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var userPreferences: UserPreferences

    @Inject
    lateinit var updateChecker: UpdateChecker

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            TrustCaptureTheme {
                var startDestination by remember { mutableStateOf<String?>(null) }
                var updateInfo by remember { mutableStateOf<AppVersionResponse?>(null) }
                var showUpdateDialog by remember { mutableStateOf(false) }

                LaunchedEffect(Unit) {
                    val hasConsent = userPreferences.hasPrivacyConsent.first()
                    val isLoggedIn = userPreferences.isLoggedIn.first()
                    startDestination = when {
                        !hasConsent -> Routes.PRIVACY_CONSENT
                        isLoggedIn -> Routes.CAMPAIGNS
                        else -> Routes.LOGIN
                    }
                }

                // Check for app updates separately (non-blocking, won't affect navigation)
                LaunchedEffect(startDestination) {
                    if (startDestination != null) {
                        val versionCheck = updateChecker.check()
                        if (versionCheck != null && versionCheck.updateAvailable) {
                            updateInfo = versionCheck
                            showUpdateDialog = true
                        }
                    }
                }

                // Update available dialog
                if (showUpdateDialog && updateInfo != null) {
                    val info = updateInfo!!
                    AlertDialog(
                        onDismissRequest = {
                            if (!info.forceUpdate) showUpdateDialog = false
                        },
                        title = { Text(if (info.forceUpdate) "Update Required" else "Update Available") },
                        text = {
                            Text(
                                info.message ?: "A new version (${info.latestVersionName}) is available. ${if (info.forceUpdate) "You must update to continue using the app." else "Update for the latest features and improvements."}"
                            )
                        },
                        confirmButton = {
                            Button(onClick = {
                                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(info.updateUrl)))
                                if (info.forceUpdate) finish()
                            }) { Text("Update Now") }
                        },
                        dismissButton = {
                            if (!info.forceUpdate) {
                                TextButton(onClick = { showUpdateDialog = false }) {
                                    Text("Later")
                                }
                            }
                        }
                    )
                }

                val navController = rememberNavController()
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    if (startDestination != null) {
                        TrustCaptureNavGraph(
                            navController = navController,
                            modifier = Modifier.padding(innerPadding),
                            startDestination = startDestination!!
                        )
                    } else {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator()
                        }
                    }
                }
            }
        }
    }
}
