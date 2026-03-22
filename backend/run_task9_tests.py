#!/usr/bin/env python3
"""Simple test runner for Task 9 tests."""

import subprocess
import sys

def run_tests():
    """Run the Task 9 tests."""
    print("Running Task 9 tests...")
    print("=" * 60)
    
    # Run signature verification tests
    print("\n1. Running signature verification tests...")
    result1 = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_signature_verification.py", "-v"],
        capture_output=True,
        text=True
    )
    print(result1.stdout)
    if result1.stderr:
        print(result1.stderr)
    
    # Run location hash tests
    print("\n2. Running location hash tests...")
    result2 = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_location_hash.py", "-v"],
        capture_output=True,
        text=True
    )
    print(result2.stdout)
    if result2.stderr:
        print(result2.stderr)
    
    # Summary
    print("\n" + "=" * 60)
    if result1.returncode == 0 and result2.returncode == 0:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
