#!/bin/bash
# Start the TrustCapture backend API

cd /home/lynksavvy/projects/trustcapture/backend

echo "Starting TrustCapture Backend API..."
echo "API will be available at: http://localhost:8000"
echo "API Documentation: http://localhost:8000/api/docs"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
