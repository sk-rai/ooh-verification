"""
Play Integrity API Service - Verifies Android device integrity via Google's Play Integrity API.

Requires:
  - GOOGLE_PLAY_INTEGRITY_ENABLED=true (env var to activate)
  - GOOGLE_SERVICE_ACCOUNT_JSON (env var: path to service account JSON file)
  - ANDROID_PACKAGE_NAME (env var: your app's package name)

When not configured, the service returns a "not_configured" verdict so the
rest of the pipeline can continue without blocking uploads.
"""
import os
import logging
import httpx
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class IntegrityVerdict:
    """Parsed Play Integrity verdict."""

    def __init__(
        self,
        device_integrity: bool = False,
        app_integrity: bool = False,
        account_integrity: bool = False,
        device_labels: list = None,
        app_recognition: str = "UNKNOWN",
        account_activity: str = "UNKNOWN",
        raw_verdict: Dict[str, Any] = None,
        error: Optional[str] = None,
    ):
        self.device_integrity = device_integrity
        self.app_integrity = app_integrity
        self.account_integrity = account_integrity
        self.device_labels = device_labels or []
        self.app_recognition = app_recognition
        self.account_activity = account_activity
        self.raw_verdict = raw_verdict or {}
        self.error = error
        self.verified_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_integrity": self.device_integrity,
            "app_integrity": self.app_integrity,
            "account_integrity": self.account_integrity,
            "device_labels": self.device_labels,
            "app_recognition": self.app_recognition,
            "account_activity": self.account_activity,
            "error": self.error,
            "verified_at": self.verified_at.isoformat(),
        }


class PlayIntegrityService:
    """
    Verifies integrity tokens from Android devices via Google Play Integrity API.

    Flow:
      1. Android app requests integrity token from Google
      2. Android sends token to POST /api/integrity/verify
      3. This service decodes the token via Google's API
      4. Returns parsed verdict (device/app/account integrity)
    """

    def __init__(self):
        self.enabled = os.getenv("GOOGLE_PLAY_INTEGRITY_ENABLED", "false").lower() == "true"
        self.package_name = os.getenv("ANDROID_PACKAGE_NAME", "")
        self.service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

        if self.enabled and self.package_name:
            logger.info(f"Play Integrity API enabled for package: {self.package_name}")
        else:
            logger.info("Play Integrity API not configured — verdicts will return 'not_configured'")

    async def verify_token(self, integrity_token: str) -> IntegrityVerdict:
        """
        Decode and verify a Play Integrity token.

        Args:
            integrity_token: The token received from the Android app's
                             IntegrityManager.requestIntegrityToken()

        Returns:
            IntegrityVerdict with parsed device/app/account integrity signals.
        """
        if not self.enabled:
            return IntegrityVerdict(error="not_configured")

        if not self.package_name:
            return IntegrityVerdict(error="package_name_not_set")

        try:
            access_token = await self._get_access_token()
            if not access_token:
                return IntegrityVerdict(error="failed_to_get_access_token")

            url = (
                f"https://playintegrity.googleapis.com/v1/"
                f"{self.package_name}:decodeIntegrityToken"
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"integrity_token": integrity_token},
                )

            if response.status_code != 200:
                logger.error(f"Play Integrity API error: {response.status_code} {response.text}")
                return IntegrityVerdict(
                    error=f"google_api_error_{response.status_code}",
                    raw_verdict={"status": response.status_code, "body": response.text},
                )

            payload = response.json().get("tokenPayloadExternal", {})
            return self._parse_verdict(payload)

        except Exception as e:
            logger.error(f"Play Integrity verification failed: {e}")
            return IntegrityVerdict(error=str(e))

    def _parse_verdict(self, payload: Dict[str, Any]) -> IntegrityVerdict:
        """Parse the tokenPayloadExternal from Google's response."""
        device_integrity = payload.get("deviceIntegrity", {})
        app_integrity = payload.get("appIntegrity", {})
        account_details = payload.get("accountDetails", {})

        device_labels = device_integrity.get("deviceRecognitionVerdict", [])
        app_recognition = app_integrity.get("appRecognitionVerdict", "UNKNOWN")
        account_activity = account_details.get("appLicensingVerdict", "UNKNOWN")

        return IntegrityVerdict(
            device_integrity="MEETS_DEVICE_INTEGRITY" in device_labels,
            app_integrity=app_recognition in ("PLAY_RECOGNIZED", "UNRECOGNIZED_VERSION"),
            account_integrity=account_activity == "LICENSED",
            device_labels=device_labels,
            app_recognition=app_recognition,
            account_activity=account_activity,
            raw_verdict=payload,
        )

    async def _get_access_token(self) -> Optional[str]:
        """
        Get a Google OAuth2 access token using service account credentials.

        TODO: Activate when Google Cloud service account is configured.
        Currently returns None — will use google-auth library or manual JWT
        exchange once GOOGLE_SERVICE_ACCOUNT_JSON is set.
        """
        # When ready, implement with google-auth:
        # from google.oauth2 import service_account
        # credentials = service_account.Credentials.from_service_account_file(
        #     self.service_account_json,
        #     scopes=["https://www.googleapis.com/auth/playintegrity"]
        # )
        # credentials.refresh(google.auth.transport.requests.Request())
        # return credentials.token
        logger.warning("Play Integrity: service account auth not yet configured")
        return None


# Singleton
_play_integrity_service: Optional[PlayIntegrityService] = None


def get_play_integrity_service() -> PlayIntegrityService:
    global _play_integrity_service
    if _play_integrity_service is None:
        _play_integrity_service = PlayIntegrityService()
    return _play_integrity_service
