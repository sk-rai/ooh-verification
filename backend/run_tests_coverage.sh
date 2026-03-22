#!/bin/bash
# Run tests with coverage and save output to log file

# Create logs directory if it doesn't exist
mkdir -p test_logs

# Generate timestamp for log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="test_logs/test_coverage_${TIMESTAMP}.log"
SUMMARY_FILE="test_logs/coverage_summary_${TIMESTAMP}.txt"

echo "=========================================="
echo "TrustCapture Test Runner with Coverage"
echo "=========================================="
echo ""
echo "Log file: $LOG_FILE"
echo "Summary file: $SUMMARY_FILE"
echo ""
echo "Running tests with coverage..."
echo ""

# Run pytest with coverage and save to log file
pytest -v --tb=short --cov=app --cov-report=term --cov-report=html --color=yes 2>&1 | tee "$LOG_FILE"

# Extract summary from log file
echo ""
echo "=========================================="
echo "Test & Coverage Summary"
echo "=========================================="
tail -30 "$LOG_FILE" | tee "$SUMMARY_FILE"

echo ""
echo "=========================================="
echo "Logs saved to:"
echo "  Full log: $LOG_FILE"
echo "  Summary: $SUMMARY_FILE"
echo "  HTML coverage: htmlcov/index.html"
echo "=========================================="
echo ""

# Create symlinks for quick access
ln -sf "$(basename $LOG_FILE)" test_logs/latest_coverage.log
echo "Quick access:"
echo "  test_logs/latest_coverage.log"
echo "  htmlcov/index.html"
