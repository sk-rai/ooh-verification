#!/usr/bin/env python3
"""Manually run the initial migration to see what happens."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import command
from alembic.config import Config


async def run_migration():
    """Run migration with detailed logging."""
    
    # Create engine with echo=True to see SQL
    engine = create_async_engine(
        "postgresql+asyncpg://trustcapture:dev_password_123@localhost:5432/trustcapture_db",
        echo=True  # This will print all SQL statements
    )
    
    try:
        # Test connection
        async with engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            print("✅ Database connection successful")
        
        # Run alembic upgrade
        print("\n🚀 Running Alembic migration...")
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(run_migration())
