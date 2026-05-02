package com.trustcapture.vendor.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.trustcapture.vendor.ui.camera.CameraScreen
import com.trustcapture.vendor.ui.campaigns.CampaignsScreen
import com.trustcapture.vendor.ui.campaigns.LocationsScreen
import com.trustcapture.vendor.ui.campaigns.LocationsViewModel
import com.trustcapture.vendor.ui.login.LoginScreen
import com.trustcapture.vendor.ui.otp.OtpScreen
import com.trustcapture.vendor.ui.privacy.PrivacyConsentScreen
import com.trustcapture.vendor.ui.settings.SettingsScreen

import java.net.URLEncoder

object Routes {
    const val PRIVACY_CONSENT = "privacy_consent"
    const val LOGIN = "login"
    const val OTP = "otp/{phoneNumber}/{vendorId}"
    const val CAMPAIGNS = "campaigns"
    const val LOCATIONS = "locations/{campaignId}/{campaignCode}/{campaignName}/{campaignType}"
    const val CAMERA = "camera/{campaignId}/{campaignCode}/{campaignType}"
    const val SETTINGS = "settings"

    fun otp(phoneNumber: String, vendorId: String) =
        "otp/${URLEncoder.encode(phoneNumber, "UTF-8")}/$vendorId"

    fun locations(campaignId: String, campaignCode: String, campaignName: String, campaignType: String) =
        "locations/$campaignId/$campaignCode/${URLEncoder.encode(campaignName, "UTF-8")}/$campaignType"

    fun camera(campaignId: String, campaignCode: String, campaignType: String) =
        "camera/$campaignId/$campaignCode/$campaignType"
}

@Composable
fun TrustCaptureNavGraph(
    navController: NavHostController,
    modifier: Modifier = Modifier,
    startDestination: String = Routes.LOGIN
) {
    NavHost(
        navController = navController,
        startDestination = startDestination,
        modifier = modifier
    ) {
        composable(Routes.PRIVACY_CONSENT) {
            PrivacyConsentScreen(
                onConsentGiven = {
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(Routes.PRIVACY_CONSENT) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.LOGIN) {
            LoginScreen(
                onOtpRequested = { phoneNumber, vendorId ->
                    navController.navigate(Routes.otp(phoneNumber, vendorId))
                },
                onLoggedIn = {
                    navController.navigate(Routes.CAMPAIGNS) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                }
            )
        }

        composable(
            route = Routes.OTP,
            arguments = listOf(
                navArgument("phoneNumber") { type = NavType.StringType },
                navArgument("vendorId") { type = NavType.StringType }
            )
        ) {
            OtpScreen(
                onVerified = {
                    navController.navigate(Routes.CAMPAIGNS) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                },
                onBack = { navController.popBackStack() }
            )
        }

        composable(Routes.CAMPAIGNS) {
            CampaignsScreen(
                onCampaignSelected = { campaignId, campaignCode, campaignType ->
                    // Navigate to locations screen; if campaign has 0 locations, it goes straight to camera
                    navController.navigate(Routes.locations(campaignId, campaignCode, campaignCode, campaignType))
                },
                onLoggedOut = {
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onSettings = {
                    navController.navigate(Routes.SETTINGS)
                }
            )
        }

        composable(
            route = Routes.LOCATIONS,
            arguments = listOf(
                navArgument("campaignId") { type = NavType.StringType },
                navArgument("campaignCode") { type = NavType.StringType },
                navArgument("campaignName") { type = NavType.StringType },
                navArgument("campaignType") { type = NavType.StringType }
            )
        ) { backStackEntry ->
            val campaignId = backStackEntry.arguments?.getString("campaignId") ?: ""
            val campaignCode = backStackEntry.arguments?.getString("campaignCode") ?: ""
            val campaignName = java.net.URLDecoder.decode(
                backStackEntry.arguments?.getString("campaignName") ?: "", "UTF-8"
            )
            val campaignType = backStackEntry.arguments?.getString("campaignType") ?: ""

            val viewModel: LocationsViewModel = hiltViewModel()
            val locations by viewModel.getLocations(campaignId).collectAsState(initial = emptyList())

            // If no locations, go straight to camera
            if (locations.isEmpty()) {
                // Show locations screen with empty state, or auto-navigate
                // We show the screen briefly — it handles the empty state
            }

            LocationsScreen(
                campaignName = campaignName,
                campaignCode = campaignCode,
                campaignType = campaignType,
                campaignId = campaignId,
                locations = locations,
                onLocationSelected = { cId, cCode, cType ->
                    navController.navigate(Routes.camera(cId, cCode, cType)) {
                        // Don't pop locations — user can go back to pick another location
                    }
                },
                onBack = { navController.popBackStack() }
            )
        }

        composable(
            route = Routes.CAMERA,
            arguments = listOf(
                navArgument("campaignId") { type = NavType.StringType },
                navArgument("campaignCode") { type = NavType.StringType },
                navArgument("campaignType") { type = NavType.StringType }
            )
        ) {
            CameraScreen(
                onBack = { navController.popBackStack() }
            )
        }

        composable(Routes.SETTINGS) {
            SettingsScreen(
                onBack = { navController.popBackStack() },
                onLoggedOut = {
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(0) { inclusive = true }
                    }
                }
            )
        }
    }
}
