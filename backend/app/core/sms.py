"""
SMS Service via Twilio.

Handles all SMS (OTP, welcome, campaign assignment) through Twilio.
Falls back to console logging if credentials are not configured.

Env vars:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
"""
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class SMSService:
    """
    Twilio-based SMS service.

    Uses Twilio for all regions (India + international).
    Falls back to console logging in dev mode when credentials aren't set.
    """

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.enabled = all([self.account_sid, self.auth_token, self.from_number])
        self.client = None

        if self.enabled:
            try:
                from twilio.rest import Client
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio SMS service initialized")
                print(f"✅ Twilio SMS initialized: from={self.from_number}")
            except ImportError:
                logger.warning("Twilio library not installed — pip install twilio")
                self.enabled = False
        else:
            logger.warning("Twilio credentials not configured — SMS will log to console")
            print(f"⚠️ Twilio not configured: SID={bool(self.account_sid)}, TOKEN={bool(self.auth_token)}, NUM={bool(self.from_number)}")

    async def send_sms(self, to_number: str, message: str) -> bool:
        """
        Send SMS via Twilio.

        Args:
            to_number: Phone number with country code (e.g. +919876543210)
            message: SMS body

        Returns:
            True if sent successfully
        """
        if self.enabled:
            try:
                msg = self.client.messages.create(
                    body=message,
                    from_=self.from_number,
                    to=to_number
                )
                logger.info(f"SMS sent to {to_number}: SID={msg.sid}")
                return True
            except Exception as e:
                logger.error(f"SMS failed to {to_number}: {e}")
                return False

        # Dev mode — log to console
        logger.info(f"[DEV SMS to {to_number}]: {message}")
        print(f"📱 [SMS to {to_number}]: {message}")
        return True

    async def send_otp_sms(self, phone_number: str, otp: str) -> bool:
        """Send OTP for vendor authentication."""
        message = f"Your TrustCapture verification code is: {otp}. Valid for 10 minutes."
        return await self.send_sms(phone_number, message)

    async def send_vendor_welcome_sms(
        self, phone_number: str, vendor_id: str, vendor_name: str
    ) -> bool:
        """Send welcome SMS to newly created vendor."""
        message = (
            f"Welcome to TrustCapture, {vendor_name}! "
            f"Your Vendor ID is: {vendor_id}. "
            f"Download the app: https://trustcapture.app/download"
        )
        return await self.send_sms(phone_number, message)

    async def send_campaign_assignment_sms(
        self, phone_number: str, vendor_name: str, campaign_name: str, campaign_code: str
    ) -> bool:
        """Send SMS when vendor is assigned to a campaign."""
        message = (
            f"Hi {vendor_name}, you've been assigned to campaign: {campaign_name} "
            f"(Code: {campaign_code}). Open the TrustCapture app to start capturing photos."
        )
        return await self.send_sms(phone_number, message)


# Global singleton
sms_service = SMSService()
