"""
Webhook handlers for payment gateways (Razorpay and Stripe).
"""
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.deps import get_db
from app.services.razorpay_service import get_razorpay_service
from app.services.stripe_service import get_stripe_service
from app.services.subscription_manager import get_subscription_manager
from app.models.subscription import SubscriptionTier

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Razorpay webhook events.
    
    Events handled:
    - subscription.activated: Subscription started
    - subscription.charged: Payment successful
    - subscription.completed: Subscription ended
    - subscription.cancelled: Subscription cancelled
    - subscription.paused: Subscription paused
    - subscription.resumed: Subscription resumed
    - payment.failed: Payment failed
    """
    try:
        # Get raw body
        body = await request.body()
        
        # Verify signature
        razorpay_service = get_razorpay_service()
        if not razorpay_service.verify_webhook_signature(body, x_razorpay_signature):
            logger.warning("Invalid Razorpay webhook signature")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Parse payload
        payload = await request.json()
        event_type = payload.get("event")
        
        logger.info(f"Received Razorpay webhook: {event_type}")
        
        # Handle event
        await razorpay_service.handle_webhook_event(db, event_type, payload.get("payload", {}))
        
        return {"status": "success"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Razorpay webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="stripe-signature"),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Stripe webhook events.
    
    Events handled:
    - customer.subscription.created: Subscription created
    - customer.subscription.updated: Subscription updated
    - customer.subscription.deleted: Subscription cancelled
    - invoice.payment_succeeded: Payment successful
    - invoice.payment_failed: Payment failed
    """
    try:
        # Get raw body
        body = await request.body()
        
        # Verify signature and construct event
        stripe_service = get_stripe_service()
        event = stripe_service.verify_webhook_signature(body, stripe_signature)
        
        logger.info(f"Received Stripe webhook: {event.type}")
        
        # Handle event
        await stripe_service.handle_webhook_event(db, event)
        
        return {"status": "success"}
    
    except ValueError as e:
        logger.warning(f"Invalid Stripe webhook: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.get("/health")
async def webhook_health():
    """Health check endpoint for webhook handlers."""
    return {
        "status": "healthy",
        "endpoints": {
            "razorpay": "/api/webhooks/razorpay",
            "stripe": "/api/webhooks/stripe"
        }
    }
