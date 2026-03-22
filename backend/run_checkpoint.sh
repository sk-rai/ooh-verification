#!/bin/bash
# Automated checkpoint script for Task 5
# This script installs dependencies and runs all tests

set -e  # Exit on error

echo "================================================================================"
echo "🧪 TrustCapture Backend - Task 5 Checkpoint"
echo "================================================================================"
echo ""

# Change to backend directory
cd "$(dirname "$0")"

echo "📦 Step 1: Installing dependencies..."
echo ""
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

echo "🧪 Step 2: Running test suite..."
echo ""
python3 -m pytest tests/ \
    -v \
    --tb=short \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html \
    --color=yes

TEST_RESULT=$?

echo ""
echo "================================================================================"

if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ CHECKPOINT PASSED - All tests passing!"
    echo ""
    echo "📊 Test Coverage:"
    echo "   - Coverage report: htmlcov/index.html"
    echo ""
    echo "📝 Next Steps:"
    echo "   - Task 5 complete"
    echo "   - Ready to proceed to Task 6 (Vendor Management API)"
else
    echo "❌ CHECKPOINT FAILED - Some tests failed"
    echo ""
    echo "💡 Debugging tips:"
    echo "   - Review test output above"
    echo "   - Run specific test: pytest tests/test_auth.py -v"
    echo "   - Check logs for errors"
fi

echo "================================================================================"

exit $TEST_RESULT
