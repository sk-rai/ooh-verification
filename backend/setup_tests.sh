#!/bin/bash
# Setup testing infrastructure for TrustCapture

echo "=========================================="
echo "TrustCapture Testing Setup"
echo "=========================================="
echo ""

# Create test directory structure
echo "1. Creating test directory structure..."
mkdir -p tests/test_api
mkdir -p tests/test_services
mkdir -p tests/test_integration
touch tests/__init__.py
touch tests/test_api/__init__.py
touch tests/test_services/__init__.py
touch tests/test_integration/__init__.py
echo "✓ Test directories created"
echo ""

# Create test database
echo "2. Creating test database..."
bash create_test_db.sh
echo ""

# Create pytest configuration
echo "3. Creating pytest configuration..."
cat > pytest.ini << 'EOF'
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
markers =
    asyncio: mark test as async
    integration: mark test as integration test
    slow: mark test as slow running
EOF
echo "✓ pytest.ini created"
echo ""

# Verify setup
echo "4. Verifying setup..."
if [ -f "tests/conftest.py" ]; then
    echo "✓ conftest.py exists"
else
    echo "✗ conftest.py missing"
fi

if [ -f "tests/test_api/test_auth.py" ]; then
    echo "✓ test_auth.py exists"
else
    echo "✗ test_auth.py missing"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run tests: pytest"
echo "2. Run with coverage: pytest --cov=app --cov-report=html"
echo "3. View coverage: open htmlcov/index.html"
echo ""
