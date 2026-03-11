"""
Email sending service with template support.

This service integrates with the email template service to send
tenant-branded emails using SendGrid or SMTP.

Requirements: 2.4, 2.5
"""
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import os

from app.services.email_template_service import EmailTemplateService

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails with template support."""
    
    def __init__(self, db: AsyncSession):
        """Initialize the email service."""
        self.db = db
        self.template_service = EmailTemplateService(db)
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = os.getenv("SMTP_PORT", 587)
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
    
    async def send_templated_email(
        self,
        tenant_id: str,
        template_name: str,
        to_email: str,
        variables: Dict[str, Any],
        from_name: Optional[str] = None,
        from_email: Optional[str] = None
    ) -> bool:
        """
        Send an email using a template.
        
        Args:
            tenant_id: UUID of the tenant
            template_name: Name of the template to use
            to_email: Recipient email address
            variables: Variables to substitute in the template
            from_name: Sender name (overrides tenant default)
            from_email: Sender email (overrides tenant default)
        
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Render template
            rendered = await self.template_service.render_template(
                tenant_id=tenant_id,
                template_name=template_name,
                variables=variables,
                format="both"
            )
            
            # Get tenant config for from_name and from_email
            if not from_name or not from_email:
                from sqlalchemy import select
                from app.models.tenant_config import TenantConfig
                
                result = await self.db.execute(
                    select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
                )
                tenant = result.scalar_one_or_none()
                
                if tenant:
                    from_name = from_name or tenant.email_from_name or "TrustCapture"
                    from_email = from_email or tenant.email_from_address or "noreply@trustcapture.com"
                else:
                    from_name = from_name or "TrustCapture"
                    from_email = from_email or "noreply@trustcapture.com"
            
            # Send email
            success = await self._send_email(
                to_email=to_email,
                from_name=from_name,
                from_email=from_email,
                subject=rendered["subject"],
                html_body=rendered.get("html_body"),
                text_body=rendered.get("text_body")
            )
            
            if success:
                logger.info(f"Email sent successfully: {template_name} to {to_email}")
            else:
                logger.error(f"Failed to send email: {template_name} to {to_email}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error sending templated email: {str(e)}")
            return False
    
    async def _send_email(
        self,
        to_email: str,
        from_name: str,
        from_email: str,
        subject: str,
        html_body: Optional[str] = None,
        text_body: Optional[str] = None
    ) -> bool:
        """
        Send email using SendGrid or SMTP.
        
        Priority:
        1. SendGrid (if API key configured)
        2. SMTP (if credentials configured)
        3. Log only (development mode)
        """
        # Try SendGrid first
        if self.sendgrid_api_key:
            return await self._send_via_sendgrid(
                to_email, from_name, from_email, subject, html_body, text_body
            )
        
        # Try SMTP
        if self.smtp_host and self.smtp_username and self.smtp_password:
            return await self._send_via_smtp(
                to_email, from_name, from_email, subject, html_body, text_body
            )
        
        # Development mode - just log
        logger.info(f"""
        [DEV MODE] Email would be sent:
        To: {to_email}
        From: {from_name} <{from_email}>
        Subject: {subject}
        HTML Body: {len(html_body) if html_body else 0} chars
        Text Body: {len(text_body) if text_body else 0} chars
        """)
        return True
    
    async def _send_via_sendgrid(
        self,
        to_email: str,
        from_name: str,
        from_email: str,
        subject: str,
        html_body: Optional[str],
        text_body: Optional[str]
    ) -> bool:
        """Send email via SendGrid API."""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Content
            
            message = Mail(
                from_email=(from_email, from_name),
                to_emails=to_email,
                subject=subject
            )
            
            if text_body:
                message.content = Content("text/plain", text_body)
            
            if html_body:
                message.content = Content("text/html", html_body)
            
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            
            return response.status_code in [200, 201, 202]
        
        except Exception as e:
            logger.error(f"SendGrid error: {str(e)}")
            return False
    
    async def _send_via_smtp(
        self,
        to_email: str,
        from_name: str,
        from_email: str,
        subject: str,
        html_body: Optional[str],
        text_body: Optional[str]
    ) -> bool:
        """Send email via SMTP."""
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{from_name} <{from_email}>"
            msg['To'] = to_email
            
            if text_body:
                msg.attach(MIMEText(text_body, 'plain'))
            
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP(self.smtp_host, int(self.smtp_port)) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            return True
        
        except Exception as e:
            logger.error(f"SMTP error: {str(e)}")
            return False


def get_email_service(db: AsyncSession) -> EmailService:
    """Dependency to get email service."""
    return EmailService(db)
