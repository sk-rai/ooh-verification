#!/usr/bin/env python3
"""
Manually add campaign_locations table to database.
Run this if alembic migration fails.
"""
import asyncio
import asyncpg

async def add_campaign_locations_table():
    """Add campaign_locations table to database."""
    
    # Database connection
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='trustcapture',
        password='dev_password_123',
        database='trustcapture_db'
    )
    
    try:
        print("🔄 Adding campaign_locations table...")
        print("=" * 60)
        
        # Create table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS campaign_locations (
                location_id UUID NOT NULL,
                campaign_id UUID NOT NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                address VARCHAR(500) NOT NULL,
                city VARCHAR(100),
                state VARCHAR(100),
                country VARCHAR(100),
                postal_code VARCHAR(20),
                latitude FLOAT NOT NULL,
                longitude FLOAT NOT NULL,
                verification_radius_meters INTEGER DEFAULT 100 NOT NULL,
                geocoding_accuracy VARCHAR(50),
                place_id VARCHAR(255),
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
                PRIMARY KEY (location_id),
                FOREIGN KEY(campaign_id) REFERENCES campaigns (campaign_id) ON DELETE CASCADE
            );
        ''')
        print("✅ Table created")
        
        # Create indexes
        print("\n🔄 Creating indexes...")
        await conn.execute('CREATE INDEX IF NOT EXISTS ix_campaign_locations_location_id ON campaign_locations(location_id);')
        await conn.execute('CREATE INDEX IF NOT EXISTS ix_campaign_locations_campaign_id ON campaign_locations(campaign_id);')
        await conn.execute('CREATE INDEX IF NOT EXISTS ix_campaign_locations_latitude ON campaign_locations(latitude);')
        await conn.execute('CREATE INDEX IF NOT EXISTS ix_campaign_locations_longitude ON campaign_locations(longitude);')
        await conn.execute('CREATE INDEX IF NOT EXISTS ix_campaign_locations_coords ON campaign_locations(latitude, longitude);')
        print("✅ Indexes created")
        
        # Update alembic version
        print("\n🔄 Updating alembic version...")
        await conn.execute("UPDATE alembic_version SET version_num = '004_campaign_locations';")
        print("✅ Alembic version updated")
        
        # Verify
        print("\n🔍 Verifying...")
        tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")
        
        print("\nAll tables:")
        for i, row in enumerate(tables, 1):
            marker = "✅" if row['tablename'] == 'campaign_locations' else "  "
            print(f"{marker} {i}. {row['tablename']}")
        
        # Check alembic version
        version = await conn.fetchval("SELECT version_num FROM alembic_version;")
        print(f"\nAlembic version: {version}")
        
        print("\n" + "=" * 60)
        print("✅ campaign_locations table added successfully!")
        print("\nYou can now start the backend:")
        print("  python3 -m uvicorn app.main:app --reload --port 8000")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(add_campaign_locations_table())
