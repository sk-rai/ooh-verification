#!/usr/bin/env python3
"""Quick verification that campaign_locations table exists."""
import asyncio
import asyncpg

async def verify():
    conn = await asyncpg.connect(
        host='localhost', port=5432, user='trustcapture',
        password='dev_password_123', database='trustcapture_db'
    )
    
    try:
        # Check table exists
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='campaign_locations');"
        )
        
        # Check alembic version
        version = await conn.fetchval("SELECT version_num FROM alembic_version;")
        
        # Count tables
        count = await conn.fetchval("SELECT COUNT(*) FROM pg_tables WHERE schemaname='public';")
        
        print("=" * 60)
        print("VERIFICATION RESULTS")
        print("=" * 60)
        print(f"✅ campaign_locations table exists: {exists}")
        print(f"✅ Alembic version: {version}")
        print(f"✅ Total tables: {count}")
        print("=" * 60)
        
        if exists and version == '004_campaign_locations':
            print("\n🎉 SUCCESS! Migration complete!")
            print("\nYou can now start the backend:")
            print("  python3 -m uvicorn app.main:app --reload --port 8000")
            print("\nThen visit: http://localhost:8000/api/docs")
        else:
            print("\n⚠️  Something is not right")
            
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(verify())
