#!/bin/bash
# Simple one-command fix for campaign_locations migration
# Just run: bash RUN_THIS_TO_FIX.sh

echo "========================================================================"
echo "Adding campaign_locations table to database"
echo "========================================================================"
echo ""

# Run the Python script
python3 add_campaign_locations_table.py

echo ""
echo "========================================================================"
echo "Done! Now you can start the backend:"
echo "  python3 -m uvicorn app.main:app --reload --port 8000"
echo "========================================================================"
