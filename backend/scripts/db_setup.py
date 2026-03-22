#!/usr/bin/env python3
"""
Database setup and management script for TrustCapture.

Usage:
    python scripts/db_setup.py init      # Initialize database
    python scripts/db_setup.py reset     # Reset database (WARNING: deletes all data)
    python scripts/db_setup.py seed      # Seed with sample data
    python scripts/db_setup.py check     # Check database connection
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import engine, init_db, close_db, AsyncSessionLocal
from app.models import (
    Client, Vendor, Campaign, LocationProfile, 
    CampaignVendorAssignment, Subscription,
    SubscriptionTier, SubscriptionStatus, VendorStatus,
    CampaignType, CampaignStatus
)
from sqlalchemy import text
from datetime import datetime, timedelta
import uuid


async def check_connection():
    """Check database connection."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print("✅ Database connection successful!")
            print(f"📊 PostgreSQL version: {version}")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


async def initialize_database():
    """Initialize database tables."""
    print("🔧 Initializing database...")
    try:
        await init_db()
        print("✅ Database tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False


async def reset_database():
    """Reset database (WARNING: deletes all data)."""
    print("⚠️  WARNING: This will delete ALL data in the database!")
    confirm = input("Type 'yes' to confirm: ")
    
    if confirm.lower() != 'yes':
        print("❌ Reset cancelled.")
        return False
    
    print("🗑️  Dropping all tables...")
    try:
        async with engine.begin() as conn:
            # Drop all tables
            await conn.run_sync(lambda sync_conn: 
                Client.metadata.drop_all(sync_conn)
            )
        print("✅ All tables dropped.")
        
        # Recreate tables
        await initialize_database()
        return True
    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        return False


async def seed_database():
    """Seed database with sample data."""
    print("🌱 Seeding database with sample data...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Create sample client
            client = Client(
                client_id=uuid.uuid4(),
                email="demo@trustcapture.com",
                password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqNqYqNqYq",  # "password123"
                company_name="Demo Company",
                phone_number="+1234567890",
                subscription_tier=SubscriptionTier.PRO,
                subscription_status=SubscriptionStatus.ACTIVE,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(client)
            await session.flush()
            
            # Create subscription
            subscription = Subscription(
                subscription_id=uuid.uuid4(),
                client_id=client.client_id,
                tier=SubscriptionTier.PRO,
                status=SubscriptionStatus.ACTIVE,
                photos_quota=999999,  # Unlimited for Pro
                photos_used=0,
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=30),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(subscription)
            
            # Create sample vendors
            vendor1 = Vendor(
                vendor_id="ABC123",
                name="John Doe",
                phone_number="+1234567891",
                email="john@example.com",
                status=VendorStatus.ACTIVE,
                created_by_client_id=client.client_id,
                created_at=datetime.utcnow()
            )
            session.add(vendor1)
            
            vendor2 = Vendor(
                vendor_id="XYZ789",
                name="Jane Smith",
                phone_number="+1234567892",
                email="jane@example.com",
                status=VendorStatus.ACTIVE,
                created_by_client_id=client.client_id,
                created_at=datetime.utcnow()
            )
            session.add(vendor2)
            await session.flush()
            
            # Create sample campaign
            campaign = Campaign(
                campaign_id=uuid.uuid4(),
                campaign_code="DEMO-2026-001",
                name="Demo Campaign",
                campaign_type=CampaignType.OOH_ADVERTISING,
                client_id=client.client_id,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=90),
                status=CampaignStatus.ACTIVE,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(campaign)
            await session.flush()
            
            # Create location profile
            location_profile = LocationProfile(
                profile_id=uuid.uuid4(),
                campaign_id=campaign.campaign_id,
                expected_latitude=12.9715987,
                expected_longitude=77.5945627,
                tolerance_meters=50.0,
                expected_wifi_bssids=["00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"],
                expected_cell_tower_ids=[12345, 67890],
                expected_pressure_min=1010.0,
                expected_pressure_max=1020.0,
                expected_light_min=10000.0,
                expected_light_max=20000.0,
                created_at=datetime.utcnow()
            )
            session.add(location_profile)
            
            # Assign vendors to campaign
            assignment1 = CampaignVendorAssignment(
                assignment_id=uuid.uuid4(),
                campaign_id=campaign.campaign_id,
                vendor_id=vendor1.vendor_id,
                assigned_at=datetime.utcnow()
            )
            session.add(assignment1)
            
            assignment2 = CampaignVendorAssignment(
                assignment_id=uuid.uuid4(),
                campaign_id=campaign.campaign_id,
                vendor_id=vendor2.vendor_id,
                assigned_at=datetime.utcnow()
            )
            session.add(assignment2)
            
            await session.commit()
            
            print("✅ Sample data created successfully!")
            print("\n📋 Sample Data:")
            print(f"   Client: {client.email} (password: password123)")
            print(f"   Vendor 1: {vendor1.vendor_id} - {vendor1.name}")
            print(f"   Vendor 2: {vendor2.vendor_id} - {vendor2.name}")
            print(f"   Campaign: {campaign.campaign_code} - {campaign.name}")
            print(f"   Location: {location_profile.expected_latitude}, {location_profile.expected_longitude}")
            
            return True
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Database seeding failed: {e}")
            return False


async def show_stats():
    """Show database statistics."""
    print("📊 Database Statistics:")
    
    async with AsyncSessionLocal() as session:
        try:
            # Count records in each table
            from sqlalchemy import select, func
            
            tables = [
                ("Clients", Client),
                ("Vendors", Vendor),
                ("Campaigns", Campaign),
                ("Location Profiles", LocationProfile),
                ("Campaign Assignments", CampaignVendorAssignment),
                ("Subscriptions", Subscription),
            ]
            
            for name, model in tables:
                result = await session.execute(select(func.count()).select_from(model))
                count = result.scalar()
                print(f"   {name}: {count}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to get statistics: {e}")
            return False


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    try:
        if command == "check":
            await check_connection()
            await show_stats()
        
        elif command == "init":
            if await check_connection():
                await initialize_database()
        
        elif command == "reset":
            if await check_connection():
                await reset_database()
        
        elif command == "seed":
            if await check_connection():
                await seed_database()
                await show_stats()
        
        else:
            print(f"❌ Unknown command: {command}")
            print(__doc__)
    
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
