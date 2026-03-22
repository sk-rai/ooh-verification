#!/bin/bash
# Script to commit essential files to git

cd /home/lynksavvy/projects/trustcapture

echo "Adding essential files to git..."

# Add backend application files
git add backend/app/
git add backend/tests/
git add backend/alembic/
git add backend/requirements.txt
git add backend/pytest.ini
git add backend/alembic.ini
git add backend/.env.example 2>/dev/null || true

# Add root documentation
git add .gitignore
git add README.md
git add TRACEABILITY_MATRIX.csv
git add TRACEABILITY_MATRIX.md
git add INDEX.md
git add DATABASE_SETUP_GUIDE.md

# Add app services (if in root)
git add app/ 2>/dev/null || true

echo ""
echo "Files added. Checking status..."
git status --short

echo ""
echo "Creating commit..."
git commit -m "Task 16 complete: Reports & Analytics API

- Added chart generation service (Plotly)
- Added map generation service (GeoJSON)
- Added report generation service (CSV, analytics)
- Added 6 new API endpoints for reports
- Added comprehensive test suite
- Updated traceability matrix
- Ready for web UI integration"

echo ""
echo "Commit created. To push to remote, run:"
echo "git push origin main"
