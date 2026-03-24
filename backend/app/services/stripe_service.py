"""
Stripe payment gateway integration service.
Handles subscription creation, management, and webhook verification for international customers.
"""
import os
import stripe
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.subscription import Subscription
from app.models.client import Client, SubscriptionTier, SubscriptionStatus


class StripeService:
    """
    Service for Stripe payment gateway integration.
    
    Supports:
    - International credit/debit cards
    - Digital wallets (Apple Pay, Google Pay)
    - Multi-currency support
    """
    
    def __init__(self):
        self.api_key = os.getenv("STRIPE_API_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        
        if not self.api_key:
            raise ValueError("Stripe API key not configured. Set STRIPE_API_KEY")
        
        stripe.api_key = self.api_key
    
    # Stripe Price IDs (to be created in Stripe dashboard)
    PRICE_IDS = {
        "free": None,  # Free tier doesn't need a price
        "pro_monthly": os.getenv("STRIPE_PRICE_PRO_MONTHLY", "price_pro_monthly"),
        "pro_yearly": os.getenv("STRIPE_PRICE_PRO_YEARLY", "price_pro_yearly"),
        "enterprise_monthly": os.getenv("STRIPE_PRICE_ENTERPRISE_MONTHLY", "price_enterprise_monthly"),
        "enterprise_yearly": os.getenv("STRIPE_PRICE_ENTERPRISE_YEARLY", "price_enterprise_yearly"),
    }
    
    # Subscription amounts in cents (USD)
    AMOUNTS = {
        SubscriptionTier.FREE: 0,
        SubscriptionTier.PRO: 1500,  # $15.00
        SubscriptionTier.ENTERPRISE: 7500,  # $75.00
    }
    
    async def create_customer(
        self,
        client_id: str,
        email: str,
        company_name: str
    ) -> str:
        """
        Create a Stripe customer.
        
        Args:
            client_id: Internal client ID
            email: Customer email
            company_name: Company name
            
        Returns:
            Stripe customer ID
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=company_name,
                metadata={
                    "client_id": str(client_id)
                }
            )
            return customer.id
        
        except Exception as e:
            raise Exception(f"Failed to create Stripe customer: {str(e)}")
    
    async def create_subscription(
        self,
        db: AsyncSession,
        client_id: str,
        tier: SubscriptionTier,
        billing_cycle: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Create a Stripe subscription.
        
        Args:
            db: Database session
            client_id: Client ID
            tier: Subscription tier
            billing_cycle: 'monthly' or 'yearly'
            
        Returns:
            Subscription details including checkout URL
        """
        # Get client
        result = await db.execute(select(Client).where(Client.client_id == client_id))
        client = result.scalar_one_or_none()
        
        if not client:
            raise ValueError("Client not found")
        
        # Free tier doesn't need Stripe subscription
        if tier == SubscriptionTier.FREE:
            return {
                "tier": "free",
                "amount": 0,
                "currency": "USD",
                "message": "Free tier activated"
            }
        
        # Create Stripe customer if not exists
        if not client.stripe_customer_id:
            customer_id = await self.create_customer(
                client_id=str(client.client_id),
                email=client.email,
                company_name=client.company_name
            )
            client.stripe_customer_id = customer_id
            await db.commit()
        else:
            customer_id = client.stripe_customer_id
        
        # Get price ID
        price_key = f"{tier.value}_{billing_cycle}"
        price_id = self.PRICE_IDS.get(price_key)
        
        if not price_id:
            raise ValueError(f"Invalid tier/billing cycle combination: {price_key}")
        
        # Create subscription
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                metadata={
                    "client_id": str(client_id),
                    "tier": tier.value
                },
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"]
            )
            
            return {
                "subscription_id": subscription.id,
                "customer_id": customer_id,
                "price_id": price_id,
                "status": subscription.status,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret,
                "amount": self.AMOUNTS[tier],
                "currency": "USD",
                "billing_cycle": billing_cycle
            }
        
        except Exception as e:
            raise Exception(f"Failed to create Stripe subscription: {str(e)}")
    
    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel a Stripe subscription.
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            Cancellation details
        """
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            return {
                "subscription_id": subscription_id,
                "status": subscription.status,
                "cancel_at": datetime.fromtimestamp(subscription.cancel_at) if subscription.cancel_at else None
            }
        
        except Exception as e:
            raise Exception(f"Failed to cancel Stripe subscription: {str(e)}")
    
    async def update_subscription(
        self,
        subscription_id: str,
        new_price_id: str
    ) -> Dict[str, Any]:
        """
        Update a Stripe subscription to a new price.
        
        Args:
            subscription_id: Stripe subscription ID
            new_price_id: New price ID
            
        Returns:
            Updated subscription details
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            stripe.Subscription.modify(
                subscription_id,
                items=[{
                    "id": subscription["items"]["data"][0].id,
                    "price": new_price_id,
                }],
                proration_behavior="create_prorations"
            )
            
            return {
                "subscription_id": subscription_id,
                "price_id": new_price_id,
                "status": subscription.status
            }
        
        except Exception as e:
            raise Exception(f"Failed to update Stripe subscription: {str(e)}")
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str
    ) -> stripe.Event:
        """
        Verify Stripe webhook signature and construct event.
        
        Args:
            payload: Raw webhook payload
            signature: Stripe-Signature header value
            
        Returns:
            Stripe Event object
        """
        if not self.webhook_secret:
            raise ValueError("Stripe webhook secret not configured")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return event
        except ValueError as e:
            raise ValueError(f"Invalid payload: {str(e)}")
        except stripe.SignatureVerificationError as e:
            raise ValueError(f"Invalid signature: {str(e)}")
    
    async def handle_webhook_event(
        self,
        db: AsyncSession,
        event: stripe.Event
    ) -> None:
        """
        Handle Stripe webhook events.
        
        Args:
            db: Database session
            event: Stripe Event object
        """
        event_type = event.type
        data = event.data.object
        
        # Handle subscription events
        if event_type.startswith("customer.subscription."):
            subscription_id = data.id
            
            # Find subscription in database
            result = await db.execute(
                select(Subscription).where(Subscription.gateway_subscription_id == subscription_id)
            )
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                return
            
            # Handle different event types
            if event_type == "customer.subscription.created":
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.current_period_start = datetime.fromtimestamp(data.current_period_start)
                subscription.current_period_end = datetime.fromtimestamp(data.current_period_end)
            
            elif event_type == "customer.subscription.updated":
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.current_period_start = datetime.fromtimestamp(data.current_period_start)
                subscription.current_period_end = datetime.fromtimestamp(data.current_period_end)
            
            elif event_type == "customer.subscription.deleted":
                subscription.status = SubscriptionStatus.CANCELLED
                subscription.cancellation_date = datetime.utcnow()
            
            await db.commit()
        
        # Handle invoice events
        elif event_type == "invoice.payment_succeeded":
            # Payment successful - subscription remains active
            pass
        
        elif event_type == "invoice.payment_failed":
            # Payment failed - mark subscription as past due
            subscription_id = data.subscription
            if subscription_id:
                result = await db.execute(
                    select(Subscription).where(Subscription.gateway_subscription_id == subscription_id)
                )
                subscription = result.scalar_one_or_none()
                if subscription:
                    subscription.status = SubscriptionStatus.PAST_DUE
                    await db.commit()


# Singleton instance
_stripe_service: Optional[StripeService] = None


def get_stripe_service() -> Optional[StripeService]:
    """Get or create Stripe service instance. Returns None if not configured."""
    global _stripe_service
    if _stripe_service is None:
        try:
            _stripe_service = StripeService()
        except ValueError:
            return None
    return _stripe_service
