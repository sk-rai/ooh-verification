#!/bin/bash
# Simple migration script for campaign_locations table
# Run this from the backend directory

echo "🔄 Running migration 004: campaign_locations"
echo "=============================================="
echo ""

cd /home/lynksavvy/projects/trustcapture/backend

# Run migration
python3 -m alembic upgrade head

echo ""
echo "=============================================="
echo "✅ Migration complete!"
echo ""
echo "Verifying..."
python3 -m alembic current

echo ""
echo "To start the backend:"
echo "  python3 -m uvicorn app.main:app --reload --port 8000"
echo ""
echo "Then visit: http://localhost:8000/api/docs"
