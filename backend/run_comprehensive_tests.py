#!/usr/bin/env python3
"""
Comprehensive Test Runner for TrustCapture Backend
Runs all test suites and generates a summary report
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

class TestRunner:
    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()
        
    def run_test_suite(self, name, test_path, description):
        """Run a test suite and capture results."""
        print(f"\n{'='*80}")
        print(f"Running: {name}")
        print(f"Description: {description}")
        print(f"Path: {test_path}")
        print(f"{'='*80}\n")
        
        try:
            result = subprocess.run(
                ['pytest', test_path, '-v', '--tb=short', '--maxfail=5'],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Parse output for pass/fail counts
            output = result.stdout + result.stderr
            
            # Extract test counts
            passed = output.count(' PASSED')
            failed = output.count(' FAILED')
            errors = output.count(' ERROR')
            skipped = output.count(' SKIPPED')
            
            self.results[name] = {
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'skipped': skipped,
                'total': passed + failed + errors + skipped,
                'return_code': result.returncode,
                'output': output
            }
            
            print(f"\n✓ {name}: {passed} passed, {failed} failed, {errors} errors, {skipped} skipped")
            
        except subprocess.TimeoutExpired:
            print(f"\n✗ {name}: TIMEOUT (>300s)")
            self.results[name] = {
                'passed': 0,
                'failed': 0,
                'errors': 1,
                'skipped': 0,
                'total': 1,
                'return_code': -1,
                'output': 'Test suite timed out'
            }
        except Exception as e:
            print(f"\n✗ {name}: ERROR - {str(e)}")
            self.results[name] = {
                'passed': 0,
                'failed': 0,
                'errors': 1,
                'skipped': 0,
                'total': 1,
                'return_code': -1,
                'output': str(e)
            }
    
    def print_summary(self):
        """Print comprehensive test summary."""
        print(f"\n\n{'='*80}")
        print("COMPREHENSIVE TEST SUMMARY")
        print(f"{'='*80}\n")
        
        total_passed = 0
        total_failed = 0
        total_errors = 0
        total_skipped = 0
        total_tests = 0
        
        print(f"{'Test Suite':<40} {'Passed':<8} {'Failed':<8} {'Errors':<8} {'Total':<8}")
        print(f"{'-'*80}")
        
        for name, result in self.results.items():
            passed = result['passed']
            failed = result['failed']
            errors = result['errors']
            total = result['total']
            
            total_passed += passed
            total_failed += failed
            total_errors += errors
            total_skipped += result['skipped']
            total_tests += total
            
            status = "✓" if result['return_code'] == 0 else "✗"
            print(f"{status} {name:<38} {passed:<8} {failed:<8} {errors:<8} {total:<8}")
        
        print(f"{'-'*80}")
        print(f"{'TOTAL':<40} {total_passed:<8} {total_failed:<8} {total_errors:<8} {total_tests:<8}")
        
        # Calculate pass rate
        if total_tests > 0:
            pass_rate = (total_passed / total_tests) * 100
            print(f"\nOverall Pass Rate: {pass_rate:.1f}%")
        
        # Time taken
        duration = datetime.now() - self.start_time
        print(f"Total Duration: {duration.total_seconds():.1f}s")
        
        print(f"\n{'='*80}\n")
        
        # Return exit code
        return 0 if total_failed == 0 and total_errors == 0 else 1

def main():
    """Run all test suites."""
    runner = TestRunner()
    
    print("\n" + "="*80)
    print("TRUSTCAPTURE COMPREHENSIVE TEST SUITE")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Working Directory: {Path.cwd()}")
    print("="*80)
    
    # Test suites to run (in order of dependency)
    test_suites = [
        # Core functionality tests
        ("Authentication", "tests/test_auth.py", "User authentication and JWT tokens"),
        ("Client Management", "tests/test_clients.py", "Client CRUD operations"),
        ("Vendor Management", "tests/test_vendor_endpoints.py", "Vendor CRUD and ID generation"),
        ("Vendor ID Generation", "tests/test_vendor_id_generation.py", "Vendor ID collision handling"),
        
        # Campaign tests
        ("Campaign Management", "tests/test_campaign_endpoints.py", "Campaign CRUD operations"),
        
        # Photo and signature tests
        ("Signature Verification", "tests/test_signature_verification.py", "Photo signature validation"),
        ("Location Hash", "tests/test_location_hash.py", "Location hash generation"),
        ("Location Matcher", "tests/test_location_profile_matcher.py", "Location profile matching"),
        ("Photo Upload", "tests/test_photo_upload.py", "Photo upload and storage"),
        
        # Audit logging
        ("Audit Logger", "tests/test_audit_logger.py", "Audit trail and hash chaining"),
        
        # Reports
        ("Reports API", "tests/test_reports_api.py", "Report generation endpoints"),
        ("Reports Service", "tests/test_reports.py", "Report generation logic"),
        ("Reports Integration", "tests/test_reports_integration.py", "End-to-end report tests"),
    ]
    
    # Run each test suite
    for name, path, description in test_suites:
        runner.run_test_suite(name, path, description)
    
    # Print summary and exit
    exit_code = runner.print_summary()
    
    # Save detailed results to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f"test_results_{timestamp}.txt"
    
    with open(report_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("TRUSTCAPTURE COMPREHENSIVE TEST RESULTS\n")
        f.write("="*80 + "\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for name, result in runner.results.items():
            f.write(f"\n{'='*80}\n")
            f.write(f"{name}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Passed: {result['passed']}\n")
            f.write(f"Failed: {result['failed']}\n")
            f.write(f"Errors: {result['errors']}\n")
            f.write(f"Skipped: {result['skipped']}\n")
            f.write(f"Total: {result['total']}\n")
            f.write(f"Return Code: {result['return_code']}\n\n")
            f.write("Output:\n")
            f.write(result['output'])
            f.write("\n\n")
    
    print(f"Detailed results saved to: {report_file}")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
