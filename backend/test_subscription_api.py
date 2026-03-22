#!/usr/bin/env python3
"""
Test script for subscription management APIs.
Tests all subscription endpoints without requiring a running server.
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid

# Add app to path
sys.path.insert(0, '/home/lynksavvy/projects/trustcapture/backend')

from app.models.client import Client
from app.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from app.services.subscription_manager import SubscriptionManager


async def setup_test_client(session: AsyncSession):
    """Create a test client with a subscription."""
    
    # Create test client
    client = Client(
        client_id=uuid.uuid4(),
        email="test@example.com",
        password_hash="hashed_password",
        company_name="Test Company",
        phone_number="+919876543210"
        subscription_tier="free",
        subscription_status="active"
        subscription_status="active",
    session.add(client)
    
    # Create free tier subscription
    subscription = Subscription(
        subscription_id=uuid.uuid4(),
        client_id=client.client_id,
        tier="free",
        status="active",
        billing_cycle="monthly",
        amount=0,
        currency="INR",
        auto_renew=True,
        vendors_quota=2,
        vendors_used=0,
        campaigns_quota=1,
        campaigns_used=0,
        storage_quota_mb=500,
        storage_used_mb=0
    )
    session.add(subscription)
    
    await session.commit()
    await session.refresh(client)
    await session.refresh(subscription)
    
    return client, subscription


async def test_subscription_apis():
    """Test all subscription management APIs."""
    
    # Create async engine
    engine = create_async_engine(
        "postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_db",
        echo=False
    )
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        print("=" * 70)
        print("SUBSCRIPTION API TESTS")
        print("=" * 70)
        
        # Setup test data
        print("\n📝 Setting up test client...")
        client, subscription = await setup_test_client(session)
        print(f"✅ Created test client: {client.email}")
        print(f"✅ Initial subscription: {subscription.tier.value} tier")
        
        # Create manager
        manager = SubscriptionManager(session)
        
        # Test 1: Get subscription
        print("\n" + "=" * 70)
        print("TEST 1: Get Current Subscription")
        print("=" * 70)
        try:
            sub = await manager.get_subscription(str(client.client_id))
            print(f"✅ Tier: {sub.tier.value}")
            print(f"✅ Status: {sub.status.value}")
            print(f"✅ Quotas: {sub.vendors_quota} vendors, {sub.campaigns_quota} campaigns")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 2: Upgrade to Pro
        print("\n" + "=" * 70)
        print("TEST 2: Upgrade to Pro Tier (Monthly)")
        print("=" * 70)
        try:
            result = await manager.upgrade_tier(
                str(client.client_id),
                "pro",
                "monthly"
            )
            print(f"✅ {result['message']}")
            print(f"✅ New tier: {result['subscription']['tier']}")
            print(f"✅ Amount: ₹{result['subscription']['amount']}")
            print(f"✅ Quotas: {result['subscription']['quotas']}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 3: Change billing cycle to yearly
        print("\n" + "=" * 70)
        print("TEST 3: Change Billing Cycle to Yearly")
        print("=" * 70)
        try:
            result = await manager.change_billing_cycle(
                str(client.client_id),
                "yearly"
            )
            print(f"✅ {result['message']}")
            print(f"✅ New amount: ₹{result['subscription']['amount']}")
            print(f"✅ Billing cycle: {result['subscription']['billing_cycle']}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 4: Upgrade to Enterprise
        print("\n" + "=" * 70)
        print("TEST 4: Upgrade to Enterprise Tier")
        print("=" * 70)
        try:
            result = await manager.upgrade_tier(
                str(client.client_id),
                "enterprise",
                "yearly"
            )
            print(f"✅ {result['message']}")
            print(f"✅ New tier: {result['subscription']['tier']}")
            print(f"✅ Amount: ₹{result['subscription']['amount']}")
            print(f"✅ Quotas: {result['subscription']['quotas']}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 5: Downgrade to Pro
        print("\n" + "=" * 70)
        print("TEST 5: Downgrade to Pro Tier")
        print("=" * 70)
        try:
            result = await manager.downgrade_tier(
                str(client.client_id),
                "pro"
            )
            print(f"✅ {result['message']}")
            print(f"✅ New tier: {result['subscription']['tier']}")
            print(f"✅ Quotas: {result['subscription']['quotas']}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 6: Cancel subscription (scheduled)
        print("\n" + "=" * 70)
        print("TEST 6: Cancel Subscription (End of Period)")
        print("=" * 70)
        try:
            result = await manager.cancel_subscription(
                str(client.client_id),
                immediate=False
            )
            print(f"✅ {result['message']}")
            print(f"✅ Status: {result['subscription']['status']}")
            print(f"✅ Access until: {result['subscription']['access_until']}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 7: Reactivate subscription
        print("\n" + "=" * 70)
        print("TEST 7: Reactivate Subscription")
        print("=" * 70)
        try:
            result = await manager.reactivate_subscription(str(client.client_id))
            print(f"✅ {result['message']}")
            print(f"✅ Status: {result['subscription']['status']}")
            print(f"✅ Tier: {result['subscription']['tier']}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 8: Try invalid downgrade (should fail)
        print("\n" + "=" * 70)
        print("TEST 8: Invalid Downgrade (Pro to Enterprise - should fail)")
        print("=" * 70)
        try:
            result = await manager.downgrade_tier(
                str(client.client_id),
                "enterprise"
            )
            print(f"❌ Should have failed but didn't!")
        except ValueError as e:
            print(f"✅ Correctly rejected: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        
        # Test 9: Immediate cancellation
        print("\n" + "=" * 70)
        print("TEST 9: Cancel Subscription (Immediate)")
        print("=" * 70)
        try:
            result = await manager.cancel_subscription(
                str(client.client_id),
                immediate=True
            )
            print(f"✅ {result['message']}")
            print(f"✅ Status: {result['subscription']['status']}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Cleanup
        print("\n" + "=" * 70)
        print("🧹 Cleaning up test data...")
        await session.delete(subscription)
        await session.delete(client)
        await session.commit()
        print("✅ Test data cleaned up")
        
        print("\n" + "=" * 70)
        print("ALL TESTS COMPLETED!")
        print("=" * 70)
    
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(test_subscription_apis())
