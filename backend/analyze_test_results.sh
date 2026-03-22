#!/bin/bash
# Analyze test results from latest log

LOG_FILE="test_logs/latest.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Error: Log file not found: $LOG_FILE"
    exit 1
fi

echo "=========================================="
echo "Test Results Analysis"
echo "=========================================="
echo ""

# Extract test summary
echo "Test Summary:"
echo "----------------------------------------"
tail -30 "$LOG_FILE" | grep -E "passed|failed|error|warning" | tail -1
echo ""

# Count results
PASSED=$(grep -c "PASSED" "$LOG_FILE" 2>/dev/null || echo "0")
FAILED=$(grep -c "FAILED" "$LOG_FILE" 2>/dev/null || echo "0")
ERRORS=$(grep -c "ERROR at setup" "$LOG_FILE" 2>/dev/null || echo "0")

echo "Detailed Counts:"
echo "  Passed: $PASSED"
echo "  Failed: $FAILED"
echo "  Errors: $ERRORS"
echo ""

# Calculate total and percentage
TOTAL=$((PASSED + FAILED + ERRORS))
if [ $TOTAL -gt 0 ]; then
    PASS_PCT=$((PASSED * 100 / TOTAL))
    echo "  Total: $TOTAL"
    echo "  Pass Rate: ${PASS_PCT}%"
fi
echo ""

# Show failed tests
echo "Failed Tests:"
echo "----------------------------------------"
grep "FAILED" "$LOG_FILE" | head -20
echo ""

# Show error tests
echo "Error Tests (first 10):"
echo "----------------------------------------"
grep "ERROR" "$LOG_FILE" | grep "test_" | head -10
echo ""

# Common error patterns
echo "Common Issues:"
echo "----------------------------------------"
echo "tenant_id violations: $(grep -c 'tenant_id.*violates not-null' $LOG_FILE)"
echo "fixture not found: $(grep -c 'fixture.*not found' $LOG_FILE)"
echo "IntegrityError: $(grep -c 'IntegrityError' $LOG_FILE)"
echo ""

echo "=========================================="
echo "Full log: $LOG_FILE"
echo "=========================================="
