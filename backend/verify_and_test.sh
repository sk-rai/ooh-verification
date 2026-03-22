#!/bin/bash
cd ~/projects/trustcapture/backend

echo "=== Clearing Python cache ==="
find tests -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find tests -name "*.pyc" -delete 2>/dev/null || true

echo ""
echo "=== Verifying conftest.py has test_tenant fixture ==="
if grep -q "async def test_tenant" tests/conftest.py; then
    echo "✓ test_tenant fixture found in conftest.py"
else
    echo "✗ test_tenant fixture NOT found in conftest.py"
    echo "Checking what's in the file:"
    head -50 tests/conftest.py
fi

echo ""
echo "=== Running pytest to list fixtures ==="
python3 -m pytest --fixtures tests/conftest.py 2>&1 | grep -A 2 "test_tenant"

echo ""
echo "=== Running a single test ==="
python3 -m pytest tests/test_api/test_auth.py::TestClientLogin::test_login_success -v
