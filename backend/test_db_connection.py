#!/usr/bin/env python3
"""Test database connection with different credentials."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_connection(url, name):
    """Test a database connection."""
    print(f"\n🔍 Testing: {name}")
    print(f"   URL: {url.replace(':' + url.split(':')[2].split('@')[0], ':****')}")
    
    try:
        engine = create_async_engine(url, echo=False)
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"   ✅ SUCCESS! Connected to PostgreSQL")
            print(f"   Version: {version[:50]}...")
            
            # Check tables
            result = await conn.execute(text(
                "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public'"
            ))
            table_count = result.scalar()
            print(f"   Tables: {table_count}")
            
            return True
    except Exception as e:
        print(f"   ❌ FAILED: {str(e)[:100]}")
        return False
    finally:
        await engine.dispose()

async def main():
    print("=" * 70)
    print("DATABASE CONNECTION TESTER")
    print("=" * 70)
    
    # Test configurations
    configs = [
        ("Current .env", os.getenv("DATABASE_URL", "postgresql+asyncpg://trustcapture:password@localhost:5432/trustcapture_db")),
        ("Password: 'password'", "postgresql+asyncpg://trustcapture:password@localhost:5432/trustcapture_db"),
        ("Password: 'dev_password_123'", "postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_db"),
        ("Test DB", "postgresql+asyncpg://test:test@localhost:5432/test_trustcapture"),
    ]
    
    success = False
    working_url = None
    
    for name, url in configs:
        if await test_connection(url, name):
            success = True
            working_url = url
            break
    
    print("\n" + "=" * 70)
    if success:
        print("✅ FOUND WORKING CONNECTION!")
        print(f"\nWorking DATABASE_URL:")
        print(f"   {working_url}")
        print(f"\n💡 Add this to your .env file:")
        print(f"   DATABASE_URL={working_url}")
    else:
        print("❌ NO WORKING CONNECTION FOUND")
        print("\n💡 Next steps:")
        print("   1. Check if PostgreSQL is running:")
        print("      sudo systemctl status postgresql")
        print()
        print("   2. Check if database exists:")
        print("      sudo -u postgres psql -l | grep trustcapture")
        print()
        print("   3. Reset password if needed:")
        print("      sudo -u postgres psql")
        print("      ALTER USER trustcapture WITH PASSWORD 'dev_password_123';")
        print("      \\q")
        print()
        print("   4. Or create database from scratch:")
        print("      sudo -u postgres psql")
        print("      CREATE DATABASE trustcapture_db;")
        print("      CREATE USER trustcapture WITH PASSWORD 'dev_password_123';")
        print("      GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;")
        print("      \\q")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
