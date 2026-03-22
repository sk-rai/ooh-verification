#!/usr/bin/env python3
"""Clear all data from test database before running tests."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

TEST_DATABASE_URL = "postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_test"

async def clear_test_database():
    """Drop and recreate all tables in test database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # Get all table names
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """))
        tables = [row[0] for row in result]
        
        if tables:
            print(f"Dropping {len(tables)} tables...")
            # Drop all tables
            for table in tables:
                await conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                print(f"  ✓ Dropped {table}")
        else:
            print("No tables to drop")
    
    await engine.dispose()
    print("\n✓ Test database cleared")

if __name__ == "__main__":
    asyncio.run(clear_test_database())
