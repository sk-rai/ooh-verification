"""
SMS utilities for sending messages via Twilio.

Provides SMS sending functionality with fallback to console logging for development.
"""
from typing import Optional
import os
from app.core.config import settings


class SMSService:
    """
    SMS service for sending messages via Twilio.
    
    Falls back to console logging if Twilio credentials are not configured.
    """
    
    def __init__(self):
        """Initialize SMS service with Twilio credentials."""
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.enabled = all([self.account_sid, self.auth_token, self.from_number])
        
        if self.enabled:
            try:
                from twilio.rest import Client
                self.client = Client(self.account_sid, self.auth_token)
            except ImportError:
                print("⚠️  Twilio library not installed. SMS will be logged to console.")
                self.enabled = False
        else:
            print("⚠️  Twilio credentials not configured. SMS will be logged to console.")
    
    async def send_vendor_welcome_sms(
        self,
        phone_number: str,
        vendor_id: str,
        vendor_name: str
    ) -> bool:
        """
        Send welcome SMS to newly created vendor with their ID and app download link.
        
        Args:
            phone_number: Vendor's phone number
            vendor_id: Generated 6-character vendor ID
            vendor_name: Vendor's name
            
        Returns:
            True if SMS sent successfully, False otherwise
            
        Requirements:
            - Req 1.3: SMS delivery with vendor ID and app download link
        """
        # Construct message
        message = (
            f"Welcome to TrustCapture, {vendor_name}! "
            f"Your Vendor ID is: {vendor_id}. "
            f"Download the app: https://trustcapture.app/download"
        )
        
        return await self.send_sms(phone_number, message)
    
    async def send_otp_sms(
        self,
        phone_number: str,
        otp: str
    ) -> bool:
        """
        Send OTP SMS for vendor authentication.
        
        Args:
            phone_number: Vendor's phone number
            otp: One-time password
            
        Returns:
            True if SMS sent successfully, False otherwise
            
        Requirements:
            - Req 1.4: OTP delivery for vendor authentication
        """
        message = f"Your TrustCapture verification code is: {otp}. Valid for 10 minutes."
        return await self.send_sms(phone_number, message)
    
    async def send_campaign_assignment_sms(
        self,
        phone_number: str,
        vendor_name: str,
        campaign_name: str,
        campaign_code: str
    ) -> bool:
        """
        Send SMS notification to vendor when assigned to a campaign.

        Args:
            phone_number: Vendor's phone number
            vendor_name: Vendor's name
            campaign_name: Campaign name
            campaign_code: Campaign code

        Returns:
            True if SMS sent successfully, False otherwise

        Requirements:
            - Req 1.3: SMS notifications for campaign assignments
        """
        message = (
            f"Hi {vendor_name}, you've been assigned to campaign: {campaign_name} "
            f"(Code: {campaign_code}). Open the TrustCapture app to start capturing photos."
        )
        return await self.send_sms(phone_number, message)
    
    async def send_sms(
        self,
        to_number: str,
        message: str
    ) -> bool:
        """
        Send SMS message.
        
        Args:
            to_number: Recipient phone number
            message: Message content
            
        Returns:
            True if SMS sent successfully, False otherwise
        """
        if self.enabled:
            try:
                msg = self.client.messages.create(
                    body=message,
                    from_=self.from_number,
                    to=to_number
                )
                print(f"✅ SMS sent to {to_number}: {msg.sid}")
                return True
            except Exception as e:
                print(f"❌ Failed to send SMS to {to_number}: {str(e)}")
                return False
        else:
            # Development mode - log to console
            print(f"📱 [SMS to {to_number}]: {message}")
            return True


# Global SMS service instance
sms_service = SMSService()
