"""
Razorpay payment gateway integration service.
Handles subscription creation, management, and webhook verification for Indian customers.
"""
import os
import hmac
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime
import razorpay
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.subscription import Subscription
from app.models.client import Client, SubscriptionTier, SubscriptionStatus


class RazorpayService:
    """
    Service for Razorpay payment gateway integration.
    
    Supports:
    - UPI payments (Google Pay, PhonePe, Paytm, BHIM)
    - Indian credit/debit cards (RuPay, Visa, Mastercard)
    - Wallets (Paytm, PhonePe, Mobikwik)
    - Net banking (all major Indian banks)
    """
    
    def __init__(self):
        self.key_id = os.getenv("RAZORPAY_KEY_ID")
        self.key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        self.webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
        
        if not self.key_id or not self.key_secret:
            raise ValueError("Razorpay credentials not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET")
        
        self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
    
    # Razorpay Plan IDs (to be created in Razorpay dashboard)
    PLAN_IDS = {
        "free": None,  # Free tier doesn't need a plan
        "pro_monthly": os.getenv("RAZORPAY_PLAN_PRO_MONTHLY", "plan_pro_monthly"),
        "pro_yearly": os.getenv("RAZORPAY_PLAN_PRO_YEARLY", "plan_pro_yearly"),
        "enterprise_monthly": os.getenv("RAZORPAY_PLAN_ENTERPRISE_MONTHLY", "plan_enterprise_monthly"),
        "enterprise_yearly": os.getenv("RAZORPAY_PLAN_ENTERPRISE_YEARLY", "plan_enterprise_yearly"),
    }
    
    # Subscription amounts in paise (INR)
    AMOUNTS = {
        SubscriptionTier.FREE: 0,
        SubscriptionTier.PRO: 99900,  # ₹999
        SubscriptionTier.ENTERPRISE: 499900,  # ₹4,999
    }
    
    async def create_customer(
        self,
        client_id: str,
        email: str,
        phone: str,
        company_name: str
    ) -> str:
        """
        Create a Razorpay customer.
        
        Args:
            client_id: Internal client ID
            email: Customer email
            phone: Customer phone number
            company_name: Company name
            
        Returns:
            Razorpay customer ID
        """
        try:
            customer_data = {
                "name": company_name,
                "email": email,
                "contact": phone,
                "notes": {
                    "client_id": str(client_id)
                }
            }
            
            customer = self.client.customer.create(data=customer_data)
            return customer["id"]
        
        except Exception as e:
            raise Exception(f"Failed to create Razorpay customer: {str(e)}")
    
    async def create_subscription(
        self,
        db: AsyncSession,
        client_id: str,
        tier: SubscriptionTier,
        billing_cycle: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Create a Razorpay subscription.
        
        Args:
            db: Database session
            client_id: Client ID
            tier: Subscription tier
            billing_cycle: 'monthly' or 'yearly'
            
        Returns:
            Subscription details including payment link
        """
        # Get client
        result = await db.execute(select(Client).where(Client.client_id == client_id))
        client = result.scalar_one_or_none()
        
        if not client:
            raise ValueError("Client not found")
        
        # Free tier doesn't need Razorpay subscription
        if tier == SubscriptionTier.FREE:
            return {
                "tier": "free",
                "amount": 0,
                "currency": "INR",
                "message": "Free tier activated"
            }
        
        # Create Razorpay customer if not exists
        if not client.stripe_customer_id:  # Reusing this field for gateway_customer_id
            customer_id = await self.create_customer(
                client_id=str(client.client_id),
                email=client.email,
                phone=client.phone_number,
                company_name=client.company_name
            )
            client.stripe_customer_id = customer_id
            await db.commit()
        else:
            customer_id = client.stripe_customer_id
        
        # Get plan ID
        plan_key = f"{tier.value}_{billing_cycle}"
        plan_id = self.PLAN_IDS.get(plan_key)
        
        if not plan_id:
            raise ValueError(f"Invalid tier/billing cycle combination: {plan_key}")
        
        # Create subscription
        try:
            subscription_data = {
                "plan_id": plan_id,
                "customer_id": customer_id,
                "quantity": 1,
                "total_count": 12 if billing_cycle == "yearly" else 0,  # 0 = until cancelled
                "notes": {
                    "client_id": str(client_id),
                    "tier": tier.value
                }
            }
            
            razorpay_subscription = self.client.subscription.create(data=subscription_data)
            
            return {
                "subscription_id": razorpay_subscription["id"],
                "customer_id": customer_id,
                "plan_id": plan_id,
                "status": razorpay_subscription["status"],
                "short_url": razorpay_subscription.get("short_url"),  # Payment link
                "amount": self.AMOUNTS[tier],
                "currency": "INR",
                "billing_cycle": billing_cycle
            }
        
        except Exception as e:
            raise Exception(f"Failed to create Razorpay subscription: {str(e)}")
    
    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel a Razorpay subscription.
        
        Args:
            subscription_id: Razorpay subscription ID
            
        Returns:
            Cancellation details
        """
        try:
            result = self.client.subscription.cancel(subscription_id, data={"cancel_at_cycle_end": 0})
            return {
                "subscription_id": subscription_id,
                "status": result["status"],
                "cancelled_at": datetime.utcnow()
            }
        
        except Exception as e:
            raise Exception(f"Failed to cancel Razorpay subscription: {str(e)}")
    
    async def update_subscription(
        self,
        subscription_id: str,
        new_plan_id: str
    ) -> Dict[str, Any]:
        """
        Update a Razorpay subscription to a new plan.
        
        Args:
            subscription_id: Razorpay subscription ID
            new_plan_id: New plan ID
            
        Returns:
            Updated subscription details
        """
        try:
            update_data = {
                "plan_id": new_plan_id,
                "quantity": 1
            }
            
            result = self.client.subscription.update(subscription_id, data=update_data)
            return {
                "subscription_id": subscription_id,
                "plan_id": new_plan_id,
                "status": result["status"]
            }
        
        except Exception as e:
            raise Exception(f"Failed to update Razorpay subscription: {str(e)}")
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str
    ) -> bool:
        """
        Verify Razorpay webhook signature.
        
        Args:
            payload: Raw webhook payload
            signature: X-Razorpay-Signature header value
            
        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            raise ValueError("Razorpay webhook secret not configured")
        
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    async def handle_webhook_event(
        self,
        db: AsyncSession,
        event_type: str,
        payload: Dict[str, Any]
    ) -> None:
        """
        Handle Razorpay webhook events.
        
        Args:
            db: Database session
            event_type: Event type (e.g., 'subscription.activated')
            payload: Event payload
        """
        subscription_data = payload.get("subscription", {})
        subscription_id = subscription_data.get("id")
        
        if not subscription_id:
            return
        
        # Find subscription in database
        result = await db.execute(
            select(Subscription).where(Subscription.gateway_subscription_id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            return
        
        # Handle different event types
        if event_type == "subscription.activated":
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.current_period_start = datetime.utcnow()
            # Set period end based on billing cycle (handled by Razorpay)
        
        elif event_type == "subscription.charged":
            # Payment successful - subscription remains active
            subscription.status = SubscriptionStatus.ACTIVE
        
        elif event_type == "subscription.completed":
            # Subscription ended naturally
            subscription.status = SubscriptionStatus.EXPIRED
            subscription.cancellation_date = datetime.utcnow()
        
        elif event_type == "subscription.cancelled":
            # Subscription cancelled
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancellation_date = datetime.utcnow()
        
        elif event_type == "subscription.paused":
            # Subscription paused
            subscription.status = SubscriptionStatus.PAST_DUE
        
        elif event_type == "subscription.resumed":
            # Subscription resumed
            subscription.status = SubscriptionStatus.ACTIVE
        
        elif event_type == "payment.failed":
            # Payment failed
            subscription.status = SubscriptionStatus.PAST_DUE
        
        await db.commit()
    
    async def create_payment_link(
        self,
        amount: int,
        currency: str,
        description: str,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a one-time payment link.
        
        Args:
            amount: Amount in smallest currency unit (paise)
            currency: Currency code (INR)
            description: Payment description
            customer_id: Optional Razorpay customer ID
            
        Returns:
            Payment link details
        """
        try:
            payment_link_data = {
                "amount": amount,
                "currency": currency,
                "description": description,
                "customer": {
                    "id": customer_id
                } if customer_id else None
            }
            
            payment_link = self.client.payment_link.create(data=payment_link_data)
            return {
                "payment_link_id": payment_link["id"],
                "short_url": payment_link["short_url"],
                "amount": amount,
                "currency": currency
            }
        
        except Exception as e:
            raise Exception(f"Failed to create payment link: {str(e)}")


# Singleton instance
_razorpay_service: Optional[RazorpayService] = None


def get_razorpay_service() -> RazorpayService:
    """Get or create Razorpay service instance."""
    global _razorpay_service
    if _razorpay_service is None:
        _razorpay_service = RazorpayService()
    return _razorpay_service
