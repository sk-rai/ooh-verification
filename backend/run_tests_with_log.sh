#!/bin/bash
# Run tests and save output to log file

# Create logs directory if it doesn't exist
mkdir -p test_logs

# Generate timestamp for log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="test_logs/test_run_${TIMESTAMP}.log"
SUMMARY_FILE="test_logs/test_summary_${TIMESTAMP}.txt"

echo "=========================================="
echo "TrustCapture Test Runner with Logging"
echo "=========================================="
echo ""
echo "Log file: $LOG_FILE"
echo "Summary file: $SUMMARY_FILE"
echo ""
echo "Running tests..."
echo ""

# Run pytest with verbose output and save to log file
pytest -v --tb=short --color=yes 2>&1 | tee "$LOG_FILE"

# Extract summary from log file
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
tail -20 "$LOG_FILE" | tee "$SUMMARY_FILE"

echo ""
echo "=========================================="
echo "Logs saved to:"
echo "  Full log: $LOG_FILE"
echo "  Summary: $SUMMARY_FILE"
echo "=========================================="
echo ""

# Also create a latest.log symlink
ln -sf "$(basename $LOG_FILE)" test_logs/latest.log
echo "Quick access: test_logs/latest.log"
