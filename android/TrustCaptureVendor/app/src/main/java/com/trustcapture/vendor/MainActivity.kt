package com.trustcapture.vendor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import com.trustcapture.vendor.data.local.datastore.UserPreferences
import com.trustcapture.vendor.ui.navigation.Routes
import com.trustcapture.vendor.ui.navigation.TrustCaptureNavGraph
import com.trustcapture.vendor.ui.theme.TrustCaptureTheme
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.flow.first
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var userPreferences: UserPreferences

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            TrustCaptureTheme {
                var startDestination by remember { mutableStateOf<String?>(null) }

                LaunchedEffect(Unit) {
                    val hasConsent = userPreferences.hasPrivacyConsent.first()
                    val isLoggedIn = userPreferences.isLoggedIn.first()
                    startDestination = when {
                        !hasConsent -> Routes.PRIVACY_CONSENT
                        isLoggedIn -> Routes.CAMPAIGNS
                        else -> Routes.LOGIN
                    }
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
