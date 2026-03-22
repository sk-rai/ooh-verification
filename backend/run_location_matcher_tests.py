#!/usr/bin/env python3
"""
Test runner for location profile matcher tests.
"""

import sys
import subprocess

if __name__ == "__main__":
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_location_profile_matcher.py", "-v"],
        cwd="/home/lynksavvy/projects/trustcapture/backend"
    )
    sys.exit(result.returncode)
