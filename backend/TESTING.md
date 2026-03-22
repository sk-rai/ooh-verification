# Testing Guide - TrustCapture Backend

## Overview

This document describes the automated testing strategy for the TrustCapture backend, including how to run tests, interpret results, and maintain test coverage.

## Test Structure

```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures and configuration
│   ├── test_auth.py          # Authentication endpoint tests
│   └── test_clients.py       # Client management endpoint tests
├── pytest.ini                # Pytest configuration
├── run_tests.py              # Python test runner
└── run_checkpoint.sh         # Bash checkpoint script
```

## Running Tests

### Method 1: Automated Checkpoint Script (Recommended)

The checkpoint script installs dependencies and runs all tests:

```bash
cd backend
./run_checkpoint.sh
```

This script will:
1. Install all required dependencies from requirements.txt
2. Run the complete test suite with coverage
3. Generate HTML coverage report
4. Display pass/fail status

### Method 2: Python Test Runner

```bash
cd backend
python3 run_tests.py
```

### Method 3: Direct Pytest

```bash
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing
```

## Test Categories

### Authentication Tests (`test_auth.py`)

Tests for authentication endpoints including:
- Client registration (success, duplicate email, weak password, invalid email)
- Client login (success, wrong password, nonexistent user)
- Vendor OTP authentication (request OTP, verify OTP, invalid credentials)
- Authenticated endpoint access (with/without tokens)

**Coverage:**
- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/vendor/request-otp
- POST /api/auth/vendor/verify-otp
- GET /api/auth/me/client
- GET /api/auth/me/vendor

### Client Management Tests (`test_clients.py`)

Tests for client profile and subscription management:
- Get client profile (authenticated/unauthenticated)
- Update profile (company name, phone number, multiple fields)
- Get subscription details
- End-to-end user flows

**Coverage:**
- GET /api/clients/me
- PATCH /api/clients/me
- GET /api/clients/me/subscription

## Test Fixtures

### Database Fixtures

- `db_session`: Fresh in-memory SQLite database for each test
- `client`: HTTP test client with database override
- `test_client`: Pre-created client in database
- `test_vendor`: Pre-created vendor in database

### Authentication Fixtures

- `client_token`: Valid JWT token for test client
- `auth_headers`: Authorization headers with JWT token

## Coverage Requirements

- **Minimum Coverage**: 70%
- **Target Coverage**: 80%+
- **Current Coverage**: Run tests to see current coverage

Coverage reports are generated in:
- Terminal: Displayed after test run
- HTML: `htmlcov/index.html`
- XML: `coverage.xml` (for CI/CD)

## Running Specific Tests

### Run single test file
```bash
pytest tests/test_auth.py -v
```

### Run single test class
```bash
pytest tests/test_auth.py::TestClientRegistration -v
```

### Run single test method
```bash
pytest tests/test_auth.py::TestClientRegistration::test_register_client_success -v
```

### Run tests matching pattern
```bash
pytest tests/ -k "login" -v
```

### Run with more verbosity
```bash
pytest tests/ -vv
```

## Test Database

Tests use an in-memory SQLite database for speed and isolation:
- Each test gets a fresh database
- Tables are created before each test
- Tables are dropped after each test
- No persistent data between tests

## Continuous Integration

The test suite is designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    cd backend
    pip install -r requirements.txt
    pytest tests/ --cov=app --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./backend/coverage.xml
```

## Writing New Tests

### Test Structure

```python
import pytest
from httpx import AsyncClient

class TestFeature:
    """Test description."""
    
    @pytest.mark.asyncio
    async def test_something(self, client: AsyncClient, auth_headers: dict):
        """Test specific behavior."""
        response = await client.get(
            "/api/endpoint",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["field"] == "expected_value"
```

### Best Practices

1. **Use descriptive test names**: `test_login_with_invalid_password_fails`
2. **Test one thing per test**: Each test should verify one specific behavior
3. **Use fixtures**: Reuse common setup code via fixtures
4. **Test edge cases**: Invalid inputs, missing data, boundary conditions
5. **Test error handling**: Verify proper error responses
6. **Test authentication**: Both authenticated and unauthenticated access
7. **Test end-to-end flows**: Complete user journeys

### Async Tests

All tests that use the HTTP client must be async:

```python
@pytest.mark.asyncio
async def test_async_endpoint(self, client: AsyncClient):
    response = await client.get("/api/endpoint")
    assert response.status_code == 200
```

## Debugging Failed Tests

### View detailed output
```bash
pytest tests/ -vv --tb=long
```

### Stop on first failure
```bash
pytest tests/ -x
```

### Run last failed tests
```bash
pytest tests/ --lf
```

### Print statements
```bash
pytest tests/ -s  # Shows print() output
```

### Use debugger
```python
import pdb; pdb.set_trace()  # Add to test code
```

## Task 5 Checkpoint Criteria

For Task 5 (Checkpoint) to pass, the following must be true:

✅ All authentication tests pass (test_auth.py)
✅ All client management tests pass (test_clients.py)
✅ Code coverage is at least 70%
✅ No critical errors or warnings
✅ All endpoints return correct status codes
✅ All endpoints return correct response formats

## Troubleshooting

### Import Errors

If you see import errors:
```bash
# Make sure you're in the backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Database Errors

If you see database errors:
```bash
# Make sure aiosqlite is installed
pip install aiosqlite

# Check that conftest.py is in tests/ directory
ls tests/conftest.py
```

### Async Errors

If you see "RuntimeError: Event loop is closed":
```bash
# Make sure pytest-asyncio is installed
pip install pytest-asyncio

# Check pytest.ini has asyncio_mode = auto
cat pytest.ini | grep asyncio_mode
```

## Next Steps

After all tests pass:
1. Review coverage report: `open htmlcov/index.html`
2. Update traceability matrix to mark Task 5 complete
3. Proceed to Task 6 (Vendor Management API)

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [HTTPX Documentation](https://www.python-httpx.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
