"""
Email template service for tenant-specific email rendering.

This service provides:
1. Default email templates for all tenants
2. Tenant-specific template overrides
3. Variable substitution using Jinja2
4. Template validation

Requirements: 2.4, 2.5
"""
from jinja2 import Template, TemplateError
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models.tenant_config import TenantConfig

logger = logging.getLogger(__name__)


# Default email templates (used when tenant doesn't have custom templates)
DEFAULT_TEMPLATES = {
    "welcome_email": {
        "subject": "Welcome to {{ tenant_name }}!",
        "html_body": """
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: {{ primary_color }}; color: white; padding: 20px; text-align: center;">
                <h1>Welcome to {{ tenant_name }}!</h1>
            </div>
            <div style="padding: 20px;">
                <p>Hello {{ user_name }},</p>
                <p>Thank you for joining {{ tenant_name }}. We're excited to have you on board!</p>
                <p>Your account has been successfully created with the email: <strong>{{ user_email }}</strong></p>
                <p>Get started by logging in to your account:</p>
                <p style="text-align: center;">
                    <a href="{{ login_url }}" style="background-color: {{ primary_color }}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                        Login to Your Account
                    </a>
                </p>
                <p>If you have any questions, feel free to reach out to our support team.</p>
                <p>Best regards,<br>The {{ tenant_name }} Team</p>
            </div>
            <div style="background-color: #f5f5f5; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                <p>&copy; {{ year }} {{ tenant_name }}. All rights reserved.</p>
            </div>
        </body>
        </html>
        """,
        "text_body": """
        Welcome to {{ tenant_name }}!
        
        Hello {{ user_name }},
        
        Thank you for joining {{ tenant_name }}. We're excited to have you on board!
        
        Your account has been successfully created with the email: {{ user_email }}
        
        Get started by logging in to your account: {{ login_url }}
        
        If you have any questions, feel free to reach out to our support team.
        
        Best regards,
        The {{ tenant_name }} Team
        
        © {{ year }} {{ tenant_name }}. All rights reserved.
        """,
        "variables": ["tenant_name", "primary_color", "user_name", "user_email", "login_url", "year"]
    },
    
    "password_reset": {
        "subject": "Reset Your {{ tenant_name }} Password",
        "html_body": """
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: {{ primary_color }}; color: white; padding: 20px; text-align: center;">
                <h1>Password Reset Request</h1>
            </div>
            <div style="padding: 20px;">
                <p>Hello {{ user_name }},</p>
                <p>We received a request to reset your password for your {{ tenant_name }} account.</p>
                <p>Click the button below to reset your password:</p>
                <p style="text-align: center;">
                    <a href="{{ reset_url }}" style="background-color: {{ primary_color }}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                        Reset Password
                    </a>
                </p>
                <p>This link will expire in {{ expiry_hours }} hours.</p>
                <p>If you didn't request a password reset, you can safely ignore this email.</p>
                <p>Best regards,<br>The {{ tenant_name }} Team</p>
            </div>
            <div style="background-color: #f5f5f5; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                <p>&copy; {{ year }} {{ tenant_name }}. All rights reserved.</p>
            </div>
        </body>
        </html>
        """,
        "text_body": """
        Password Reset Request
        
        Hello {{ user_name }},
        
        We received a request to reset your password for your {{ tenant_name }} account.
        
        Click the link below to reset your password:
        {{ reset_url }}
        
        This link will expire in {{ expiry_hours }} hours.
        
        If you didn't request a password reset, you can safely ignore this email.
        
        Best regards,
        The {{ tenant_name }} Team
        
        © {{ year }} {{ tenant_name }}. All rights reserved.
        """,
        "variables": ["tenant_name", "primary_color", "user_name", "reset_url", "expiry_hours", "year"]
    },
    
    "photo_approved": {
        "subject": "Photo Approved - {{ campaign_name }}",
        "html_body": """
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: {{ secondary_color }}; color: white; padding: 20px; text-align: center;">
                <h1>✓ Photo Approved</h1>
            </div>
            <div style="padding: 20px;">
                <p>Hello {{ vendor_name }},</p>
                <p>Great news! Your photo for campaign <strong>{{ campaign_name }}</strong> has been approved.</p>
                <p><strong>Photo Details:</strong></p>
                <ul>
                    <li>Campaign: {{ campaign_name }}</li>
                    <li>Submitted: {{ submission_date }}</li>
                    <li>Status: Approved</li>
                </ul>
                <p>Thank you for your contribution!</p>
                <p>Best regards,<br>The {{ tenant_name }} Team</p>
            </div>
            <div style="background-color: #f5f5f5; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                <p>&copy; {{ year }} {{ tenant_name }}. All rights reserved.</p>
            </div>
        </body>
        </html>
        """,
        "text_body": """
        Photo Approved
        
        Hello {{ vendor_name }},
        
        Great news! Your photo for campaign {{ campaign_name }} has been approved.
        
        Photo Details:
        - Campaign: {{ campaign_name }}
        - Submitted: {{ submission_date }}
        - Status: Approved
        
        Thank you for your contribution!
        
        Best regards,
        The {{ tenant_name }} Team
        
        © {{ year }} {{ tenant_name }}. All rights reserved.
        """,
        "variables": ["tenant_name", "secondary_color", "vendor_name", "campaign_name", "submission_date", "year"]
    },
    
    "photo_rejected": {
        "subject": "Photo Requires Attention - {{ campaign_name }}",
        "html_body": """
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #EF4444; color: white; padding: 20px; text-align: center;">
                <h1>Photo Requires Attention</h1>
            </div>
            <div style="padding: 20px;">
                <p>Hello {{ vendor_name }},</p>
                <p>Your photo for campaign <strong>{{ campaign_name }}</strong> requires attention.</p>
                <p><strong>Photo Details:</strong></p>
                <ul>
                    <li>Campaign: {{ campaign_name }}</li>
                    <li>Submitted: {{ submission_date }}</li>
                    <li>Status: {{ status }}</li>
                </ul>
                <p><strong>Reason:</strong> {{ rejection_reason }}</p>
                <p>Please review and resubmit if necessary.</p>
                <p>Best regards,<br>The {{ tenant_name }} Team</p>
            </div>
            <div style="background-color: #f5f5f5; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                <p>&copy; {{ year }} {{ tenant_name }}. All rights reserved.</p>
            </div>
        </body>
        </html>
        """,
        "text_body": """
        Photo Requires Attention
        
        Hello {{ vendor_name }},
        
        Your photo for campaign {{ campaign_name }} requires attention.
        
        Photo Details:
        - Campaign: {{ campaign_name }}
        - Submitted: {{ submission_date }}
        - Status: {{ status }}
        
        Reason: {{ rejection_reason }}
        
        Please review and resubmit if necessary.
        
        Best regards,
        The {{ tenant_name }} Team
        
        © {{ year }} {{ tenant_name }}. All rights reserved.
        """,
        "variables": ["tenant_name", "vendor_name", "campaign_name", "submission_date", "status", "rejection_reason", "year"]
    },
    
    "subscription_expiring": {
        "subject": "Your {{ tenant_name }} Subscription is Expiring Soon",
        "html_body": """
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: {{ primary_color }}; color: white; padding: 20px; text-align: center;">
                <h1>Subscription Expiring Soon</h1>
            </div>
            <div style="padding: 20px;">
                <p>Hello {{ user_name }},</p>
                <p>Your {{ tenant_name }} subscription will expire in <strong>{{ days_remaining }} days</strong>.</p>
                <p><strong>Subscription Details:</strong></p>
                <ul>
                    <li>Plan: {{ plan_name }}</li>
                    <li>Expiry Date: {{ expiry_date }}</li>
                </ul>
                <p>To continue enjoying uninterrupted service, please renew your subscription:</p>
                <p style="text-align: center;">
                    <a href="{{ renewal_url }}" style="background-color: {{ primary_color }}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                        Renew Subscription
                    </a>
                </p>
                <p>If you have any questions, please contact our support team.</p>
                <p>Best regards,<br>The {{ tenant_name }} Team</p>
            </div>
            <div style="background-color: #f5f5f5; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                <p>&copy; {{ year }} {{ tenant_name }}. All rights reserved.</p>
            </div>
        </body>
        </html>
        """,
        "text_body": """
        Subscription Expiring Soon
        
        Hello {{ user_name }},
        
        Your {{ tenant_name }} subscription will expire in {{ days_remaining }} days.
        
        Subscription Details:
        - Plan: {{ plan_name }}
        - Expiry Date: {{ expiry_date }}
        
        To continue enjoying uninterrupted service, please renew your subscription:
        {{ renewal_url }}
        
        If you have any questions, please contact our support team.
        
        Best regards,
        The {{ tenant_name }} Team
        
        © {{ year }} {{ tenant_name }}. All rights reserved.
        """,
        "variables": ["tenant_name", "primary_color", "user_name", "days_remaining", "plan_name", "expiry_date", "renewal_url", "year"]
    }
}


class EmailTemplateService:
    """Service for rendering tenant-specific email templates."""
    
    def __init__(self, db: AsyncSession):
        """Initialize the email template service."""
        self.db = db
    
    async def render_template(
        self,
        tenant_id: str,
        template_name: str,
        variables: Dict[str, Any],
        format: str = "html"
    ) -> Dict[str, str]:
        """
        Render an email template with variables.
        
        Args:
            tenant_id: UUID of the tenant
            template_name: Name of the template (e.g., 'welcome_email')
            variables: Dictionary of variables to substitute
            format: 'html' or 'text' or 'both'
        
        Returns:
            Dictionary with 'subject', 'html_body', and/or 'text_body'
        
        Raises:
            ValueError: If template not found or rendering fails
        """
        # Get tenant configuration
        result = await self.db.execute(
            select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Get template (tenant-specific or default)
        template_data = await self._get_template(tenant, template_name)
        
        if not template_data:
            raise ValueError(f"Template '{template_name}' not found")
        
        # Add tenant branding to variables
        variables.update({
            "tenant_name": tenant.tenant_name if tenant else "TrustCapture",
            "primary_color": (tenant.primary_color if tenant else None) or "#3B82F6",
            "secondary_color": (tenant.secondary_color if tenant else None) or "#10B981",
        })
        
        # Add current year if not provided
        if "year" not in variables:
            from datetime import datetime
            variables["year"] = datetime.utcnow().year
        
        # Render templates
        result = {}
        
        try:
            # Render subject
            subject_template = Template(template_data["subject"])
            result["subject"] = subject_template.render(**variables)
            
            # Render HTML body
            if format in ["html", "both"]:
                html_template = Template(template_data["html_body"])
                result["html_body"] = html_template.render(**variables)
            
            # Render text body
            if format in ["text", "both"]:
                text_template = Template(template_data["text_body"])
                result["text_body"] = text_template.render(**variables)
        
        except TemplateError as e:
            logger.error(f"Template rendering error: {str(e)}")
            raise ValueError(f"Failed to render template: {str(e)}")
        
        return result
    
    async def _get_template(
        self,
        tenant: TenantConfig,
        template_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get template data (tenant-specific or default).
        
        Priority:
        1. Tenant-specific template (from tenant.email_templates)
        2. Default template
        """
        # Check for tenant-specific template
        if tenant.email_templates and template_name in tenant.email_templates:
            return tenant.email_templates[template_name]
        
        # Fall back to default template
        if template_name in DEFAULT_TEMPLATES:
            return DEFAULT_TEMPLATES[template_name]
        
        return None
    
    async def get_available_templates(self) -> Dict[str, list]:
        """
        Get list of available templates.
        
        Returns:
            Dictionary with template names and their required variables
        """
        templates = {}
        for name, data in DEFAULT_TEMPLATES.items():
            templates[name] = {
                "name": name,
                "variables": data.get("variables", []),
                "description": f"Template for {name.replace('_', ' ')}"
            }
        return templates
    
    async def validate_template(
        self,
        template_data: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate template structure and syntax.
        
        Args:
            template_data: Template dictionary with subject, html_body, text_body
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ["subject", "html_body", "text_body"]
        
        # Check required fields
        for field in required_fields:
            if field not in template_data:
                return False, f"Missing required field: {field}"
        
        # Validate Jinja2 syntax
        try:
            Template(template_data["subject"])
            Template(template_data["html_body"])
            Template(template_data["text_body"])
        except TemplateError as e:
            return False, f"Template syntax error: {str(e)}"
        
        return True, None


def get_email_template_service(db: AsyncSession) -> EmailTemplateService:
    """Dependency to get email template service."""
    return EmailTemplateService(db)
