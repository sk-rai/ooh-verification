#!/usr/bin/env python3
"""
Run photo upload tests.
"""
import subprocess
import sys

def main():
    """Run photo upload tests."""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_photo_upload.py",
        "-v",
        "--tb=short"
    ]
    
    result = subprocess.run(cmd, cwd=".")
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
