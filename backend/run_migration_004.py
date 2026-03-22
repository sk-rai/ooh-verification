#!/usr/bin/env python3
"""
Run migration 004 to add campaign_locations table.
"""
import subprocess
import sys
import os

# Change to backend directory
os.chdir('/home/lynksavvy/projects/trustcapture/backend')

print("🔄 Running Alembic migration to add campaign_locations table...")
print("=" * 60)

# Run alembic upgrade
result = subprocess.run(
    [sys.executable, '-m', 'alembic', 'upgrade', 'head'],
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    print(result.stderr)

if result.returncode == 0:
    print("=" * 60)
    print("✅ Migration completed successfully!")
    print("\nVerifying tables...")
    
    # Verify the table was created
    verify_result = subprocess.run(
        [
            'psql',
            '-U', 'trustcapture',
            '-h', 'localhost',
            '-d', 'trustcapture_db',
            '-c', "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
        ],
        capture_output=True,
        text=True,
        env={**os.environ, 'PGPASSWORD': 'dev_password_123'}
    )
    
    print(verify_result.stdout)
    
    if 'campaign_locations' in verify_result.stdout:
        print("✅ campaign_locations table created successfully!")
    else:
        print("⚠️  campaign_locations table not found in database")
else:
    print("=" * 60)
    print("❌ Migration failed!")
    sys.exit(1)
