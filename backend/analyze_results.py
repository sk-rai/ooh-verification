#!/usr/bin/env python3
"""Analyze test results from log file."""

import re
import sys
from pathlib import Path

def analyze_test_log(log_file="test_logs/latest.log"):
    """Analyze test results from log file."""
    
    log_path = Path(log_file)
    if not log_path.exists():
        print(f"Error: Log file not found: {log_file}")
        return
    
    with open(log_path, 'r') as f:
        content = f.read()
    
    print("=" * 60)
    print("TEST RESULTS ANALYSIS")
    print("=" * 60)
    print()
    
    # Extract summary line
    summary_match = re.search(r'=+ ([\d\w\s,()]+) in [\d.]+s', content)
    if summary_match:
        print("Summary:")
        print(f"  {summary_match.group(1)}")
        print()
    
    # Count test results
    passed = len(re.findall(r'PASSED', content))
    failed = len(re.findall(r'FAILED', content))
    errors = len(re.findall(r'ERROR at setup', content))
    
    total = passed + failed + errors
    
    print("Detailed Counts:")
    print(f"  ✓ Passed: {passed}")
    print(f"  ✗ Failed: {failed}")
    print(f"  ⚠ Errors: {errors}")
    print(f"  Total: {total}")
    
    if total > 0:
        pass_rate = (passed / total) * 100
        print(f"  Pass Rate: {pass_rate:.1f}%")
    print()
    
    # Find failed tests
    failed_tests = re.findall(r'FAILED (tests/[^\s]+)', content)
    if failed_tests:
        print(f"Failed Tests ({len(failed_tests)}):")
        print("-" * 60)
        for test in failed_tests[:20]:
            print(f"  • {test}")
        if len(failed_tests) > 20:
            print(f"  ... and {len(failed_tests) - 20} more")
        print()
    
    # Find error tests
    error_tests = re.findall(r'ERROR (tests/[^\s]+)', content)
    if error_tests:
        print(f"Error Tests ({len(error_tests)}):")
        print("-" * 60)
        for test in error_tests[:10]:
            print(f"  • {test}")
        if len(error_tests) > 10:
            print(f"  ... and {len(error_tests) - 10} more")
        print()
    
    # Common error patterns
    print("Common Issues:")
    print("-" * 60)
    
    tenant_id_errors = len(re.findall(r'tenant_id.*violates not-null', content))
    fixture_errors = len(re.findall(r'fixture.*not found', content))
    integrity_errors = len(re.findall(r'IntegrityError', content))
    
    if tenant_id_errors:
        print(f"  • tenant_id NULL violations: {tenant_id_errors}")
    if fixture_errors:
        print(f"  • Missing fixtures: {fixture_errors}")
    if integrity_errors:
        print(f"  • Integrity errors: {integrity_errors}")
    
    if not (tenant_id_errors or fixture_errors or integrity_errors):
        print("  No common issues detected")
    print()
    
    # Improvement suggestions
    print("=" * 60)
    if passed > 0 and total > 0:
        if pass_rate >= 90:
            print("✓ Excellent! Test suite is in great shape!")
        elif pass_rate >= 75:
            print("✓ Good progress! A few more fixes needed.")
        elif pass_rate >= 50:
            print("⚠ Making progress. Focus on fixing errors.")
        else:
            print("⚠ Needs attention. Many tests failing.")
    print("=" * 60)

if __name__ == "__main__":
    log_file = sys.argv[1] if len(sys.argv) > 1 else "test_logs/latest.log"
    analyze_test_log(log_file)
