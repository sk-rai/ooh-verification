#!/usr/bin/env python3
"""
Automated test runner for TrustCapture backend.

This script runs all tests and generates a comprehensive report.
"""
import subprocess
import sys
import os
from pathlib import Path


def run_tests():
    """Run all tests with pytest."""
    print("=" * 80)
    print("🧪 TrustCapture Backend - Automated Test Suite")
    print("=" * 80)
    print()
    
    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    # Check if pytest is installed
    try:
        import pytest
    except ImportError:
        print("❌ pytest is not installed!")
        print("   Install it with: pip install pytest pytest-asyncio pytest-cov httpx")
        return False
    
    # Run pytest
    print("📋 Running tests...")
    print()
    
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "tests/",
            "-v",
            "--tb=short",
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--color=yes"
        ],
        capture_output=False
    )
    
    print()
    print("=" * 80)
    
    if result.returncode == 0:
        print("✅ All tests passed!")
        print()
        print("📊 Coverage report generated:")
        print("   - Terminal: See above")
        print("   - HTML: Open htmlcov/index.html in your browser")
        print()
        return True
    else:
        print("❌ Some tests failed!")
        print()
        print("💡 Tips:")
        print("   - Check the test output above for details")
        print("   - Run specific test: pytest tests/test_auth.py::TestClientLogin::test_login_success")
        print("   - Run with more detail: pytest tests/ -vv")
        print()
        return False


def check_dependencies():
    """Check if all required dependencies are installed."""
    print("🔍 Checking dependencies...")
    
    required = [
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "httpx",
        "sqlalchemy",
        "fastapi"
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print()
        print("Install them with:")
        print(f"   pip install {' '.join(missing)}")
        print()
        return False
    
    print("✅ All dependencies installed")
    print()
    return True


def main():
    """Main entry point."""
    if not check_dependencies():
        sys.exit(1)
    
    success = run_tests()
    
    if success:
        print("=" * 80)
        print("🎉 Checkpoint passed! All tests are passing.")
        print("=" * 80)
        sys.exit(0)
    else:
        print("=" * 80)
        print("⚠️  Checkpoint failed! Please fix failing tests.")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
