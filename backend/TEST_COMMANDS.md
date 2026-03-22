# Test Commands - Quick Reference

## Run Tests

```bash
# Basic test run with logging
bash run_tests_with_log.sh

# Test run with coverage
bash run_tests_coverage.sh

# Run without logging (direct)
pytest -v

# Run specific test file
pytest tests/test_api/test_auth.py -v

# Run specific test
pytest tests/test_api/test_auth.py::TestClientRegistration::test_register_success -v
```

## View Logs

```bash
# View latest test log
cat test_logs/latest.log

# View latest summary
tail -20 test_logs/latest.log

# View coverage log
cat test_logs/latest_coverage.log

# Open coverage HTML
xdg-open htmlcov/index.html
```

## Analyze Results

```bash
# Count passed tests
grep "PASSED" test_logs/latest.log | wc -l

# Count failed tests
grep "FAILED" test_logs/latest.log | wc -l

# Show only failures
grep "FAILED\|ERROR" test_logs/latest.log

# Show test summary
tail -30 test_logs/latest.log
```

## Coverage

```bash
# Run with coverage
pytest --cov=app --cov-report=html

# View coverage percentage
pytest --cov=app --cov-report=term

# Coverage for specific module
pytest --cov=app.api --cov-report=term
```

## Test Selection

```bash
# Run only API tests
pytest tests/test_api/ -v

# Run only unit tests
pytest -m unit -v

# Run only integration tests
pytest -m integration -v

# Run tests matching pattern
pytest -k "auth" -v

# Run failed tests from last run
pytest --lf -v

# Run failed tests first, then others
pytest --ff -v
```

## Debugging

```bash
# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l

# Enter debugger on failure
pytest --pdb

# Verbose output with full traceback
pytest -vv --tb=long
```

## Performance

```bash
# Show slowest 10 tests
pytest --durations=10

# Run tests in parallel (if pytest-xdist installed)
pytest -n auto
```

## Clean Up

```bash
# Remove old logs (7+ days)
find test_logs -name "*.log" -mtime +7 -delete

# Remove coverage files
rm -rf htmlcov/ .coverage

# Remove pytest cache
rm -rf .pytest_cache/
```
