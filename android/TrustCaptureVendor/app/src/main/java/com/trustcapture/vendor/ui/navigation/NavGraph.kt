package com.trustcapture.vendor.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.trustcapture.vendor.ui.camera.CameraScreen
import com.trustcapture.vendor.ui.campaigns.CampaignsScreen
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
    const val CAMERA = "camera/{campaignId}/{campaignCode}/{campaignType}"
    const val SETTINGS = "settings"

    fun otp(phoneNumber: String, vendorId: String) =
        "otp/${URLEncoder.encode(phoneNumber, "UTF-8")}/$vendorId"

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
                    navController.navigate(Routes.camera(campaignId, campaignCode, campaignType))
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
