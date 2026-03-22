#!/usr/bin/env python3
"""Test if migrations actually create tables."""

import asyncio
import asyncpg


async def check_database():
    """Check what's in the database."""
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='trustcapture',
        password='dev_password_123',
        database='trustcapture_db'
    )
    
    try:
        # Check tables
        tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """)
        
        print(f"\n📊 Tables in database: {len(tables)}")
        for table in tables:
            print(f"  - {table['tablename']}")
        
        # Check enum types
        enums = await conn.fetch("""
            SELECT typname 
            FROM pg_type 
            WHERE typtype = 'e' 
            ORDER BY typname
        """)
        
        print(f"\n🔤 Enum types: {len(enums)}")
        for enum in enums:
            print(f"  - {enum['typname']}")
        
        # Check alembic version
        try:
            version = await conn.fetchval("SELECT version_num FROM alembic_version")
            print(f"\n📌 Alembic version: {version}")
        except:
            print("\n📌 Alembic version: Not set (no alembic_version table)")
        
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(check_database())
