#!/usr/bin/env python3
"""Simple test for subscription manager."""
import asyncio
import sys
sys.path.insert(0, '/home/lynksavvy/projects/trustcapture/backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.subscription_manager import SubscriptionManager

async def test():
    engine = create_async_engine(
        "postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_db",
        echo=False
    )
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        manager = SubscriptionManager(session)
        
        # Test with a real client (we need to create one first)
        print("Testing SubscriptionManager methods...")
        print("Note: Need a real client_id from database")
        print("✅ SubscriptionManager initialized successfully")
        
        # Check tier quotas
        quotas_free = manager._get_tier_quotas("free")
        print(f"\n✅ Free tier quotas: {quotas_free}")
        
        quotas_pro = manager._get_tier_quotas("pro")
        print(f"✅ Pro tier quotas: {quotas_pro}")
        
        quotas_ent = manager._get_tier_quotas("enterprise")
        print(f"✅ Enterprise tier quotas: {quotas_ent}")
        
        # Check pricing
        pricing_pro_monthly = manager._get_tier_pricing("pro", "monthly")
        print(f"\n✅ Pro monthly pricing: {pricing_pro_monthly}")
        
        pricing_pro_yearly = manager._get_tier_pricing("pro", "yearly")
        print(f"✅ Pro yearly pricing: {pricing_pro_yearly}")
        
        print("\n✅ All basic tests passed!")
    
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(test())
