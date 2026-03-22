#!/usr/bin/env python3
"""
Comprehensive Checkpoint Test Script

Tests everything since last checkpoint:
1. Database schema and migrations
2. Backend API endpoints (all routes)
3. Multi-tenancy implementation
4. Tenant isolation
5. Email template system
6. Frontend integration (branding API)

This is a complete validation of Phase 1 implementation.
"""
import asyncio
import httpx
import sys
import json
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any, List, Tuple

# Configuration
BASE_URL = "http://localhost:8000"
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "trustcapture_db",
    "user": "trustcapture",
    "password": "dev_password_123"
}

# Test results
test_results: List[Tuple[str, bool, str]] = []
test_data: Dict[str, Any] = {}


def log_test(test_name: str, passed: bool, message: str = ""):
    """Log test result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    test_results.append((test_name, passed, message))
    print(f"{status}: {test_name}")
    if message:
        print(f"  {message}")


def print_section(title: str):
    """Print section header."""
    print("\n" + "="*80)
    print(title)
    print("="*80)



async def test_database_schema():
    """Test 1: Database schema verification."""
    print_section("TEST 1: Database Schema Verification")
    
    try:
        import asyncpg
        
        conn = await asyncpg.connect(**DB_CONFIG)
        
        # Check migration version
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        log_test("Migration version", version == "005_tenant_config", f"Current: {version}")
        
        # Check tenant_config table
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'tenant_config'
            )
        """)
        log_test("tenant_config table exists", result)
        
        # Check all tables have tenant_id
        tables = ['clients', 'vendors', 'campaigns', 'photos', 'audit_logs', 
                 'subscriptions', 'campaign_locations']
        
        for table in tables:
            result = await conn.fetchval(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = '{table}' AND column_name = 'tenant_id'
                )
            """)
            log_test(f"{table}.tenant_id exists", result)
        
        # Check default tenant
        default_tenant = await conn.fetchrow(
            "SELECT * FROM tenant_config WHERE subdomain = 'default'"
        )
        log_test("Default tenant exists", default_tenant is not None)
        
        if default_tenant:
            test_data['default_tenant_id'] = str(default_tenant['tenant_id'])
        
        await conn.close()
        return True
    
    except Exception as e:
        log_test("Database schema test", False, str(e))
        return False



async def test_tenant_management():
    """Test 2: Tenant management API."""
    print_section("TEST 2: Tenant Management API")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            # Create test tenant
            tenant_data = {
                "tenant_name": "Test Corp",
                "subdomain": f"test{uuid4().hex[:8]}",
                "logo_url": "https://example.com/logo.png",
                "primary_color": "#FF5733",
                "secondary_color": "#33FF57",
                "email_from_name": "Test Corp",
                "email_from_address": "noreply@testcorp.com"
            }
            
            response = await client.post("/api/admin/tenants", json=tenant_data)
            log_test("Create tenant", response.status_code == 201)
            
            if response.status_code == 201:
                tenant = response.json()
                test_data['test_tenant_id'] = tenant['tenant_id']
                test_data['test_subdomain'] = tenant['subdomain']
                
                # Get tenant
                response = await client.get(f"/api/admin/tenants/{tenant['tenant_id']}")
                log_test("Get tenant by ID", response.status_code == 200)
                
                # List tenants
                response = await client.get("/api/admin/tenants")
                log_test("List tenants", response.status_code == 200)
                
                # Update tenant
                response = await client.put(
                    f"/api/admin/tenants/{tenant['tenant_id']}",
                    json={"tenant_name": "Updated Test Corp"}
                )
                log_test("Update tenant", response.status_code == 200)
                
                return True
            
            return False
        
        except Exception as e:
            log_test("Tenant management test", False, str(e))
            return False



async def test_auth_flow():
    """Test 3: Authentication flow with tenant context."""
    print_section("TEST 3: Authentication Flow")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            tenant_id = test_data.get('test_tenant_id') or test_data.get('default_tenant_id')
            headers = {"X-Tenant-ID": tenant_id}
            
            # Register client
            client_data = {
                "email": f"test_{uuid4().hex[:8]}@example.com",
                "password": "Test123!@#",
                "company_name": "Test Company",
                "phone_number": "+1234567890"
            }
            
            response = await client.post("/api/auth/register", json=client_data, headers=headers)
            log_test("Register client", response.status_code == 201)
            
            if response.status_code == 201:
                client_info = response.json()
                test_data['test_client_email'] = client_data['email']
                test_data['test_client_password'] = client_data['password']
                
                # Login
                login_data = {
                    "email": client_data['email'],
                    "password": client_data['password']
                }
                
                response = await client.post("/api/auth/login", json=login_data, headers=headers)
                log_test("Login client", response.status_code == 200)
                
                if response.status_code == 200:
                    token_data = response.json()
                    test_data['access_token'] = token_data['access_token']
                    log_test("Received access token", 'access_token' in token_data)
                    
                    # Get current client info
                    auth_headers = {
                        "Authorization": f"Bearer {token_data['access_token']}",
                        "X-Tenant-ID": tenant_id
                    }
                    
                    response = await client.get("/api/auth/me/client", headers=auth_headers)
                    log_test("Get current client info", response.status_code == 200)
                    
                    return True
            
            return False
        
        except Exception as e:
            log_test("Auth flow test", False, str(e))
            return False



async def test_vendor_management():
    """Test 4: Vendor management with tenant isolation."""
    print_section("TEST 4: Vendor Management")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            tenant_id = test_data.get('test_tenant_id') or test_data.get('default_tenant_id')
            token = test_data.get('access_token')
            
            if not token:
                log_test("Vendor management test", False, "No access token available")
                return False
            
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": tenant_id
            }
            
            # Create vendor
            vendor_data = {
                "name": "Test Vendor",
                "phone_number": "+1111111111",
                "email": "vendor@example.com"
            }
            
            response = await client.post("/api/vendors", json=vendor_data, headers=headers)
            log_test("Create vendor", response.status_code == 201)
            
            if response.status_code == 201:
                vendor = response.json()
                test_data['vendor_id'] = vendor['vendor_id']
                
                # List vendors
                response = await client.get("/api/vendors", headers=headers)
                log_test("List vendors", response.status_code == 200)
                
                if response.status_code == 200:
                    vendors = response.json()
                    log_test("Vendors list contains created vendor", 
                            len(vendors.get('vendors', [])) > 0)
                
                # Update vendor
                update_data = {"name": "Updated Vendor"}
                response = await client.patch(
                    f"/api/vendors/{vendor['vendor_id']}", 
                    json=update_data, 
                    headers=headers
                )
                log_test("Update vendor", response.status_code == 200)
                
                return True
            
            return False
        
        except Exception as e:
            log_test("Vendor management test", False, str(e))
            return False



async def test_campaign_management():
    """Test 5: Campaign management with tenant isolation."""
    print_section("TEST 5: Campaign Management")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            tenant_id = test_data.get('test_tenant_id') or test_data.get('default_tenant_id')
            token = test_data.get('access_token')
            
            if not token:
                log_test("Campaign management test", False, "No access token")
                return False
            
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": tenant_id
            }
            
            # Create campaign
            campaign_data = {
                "name": "Test Campaign",
                "campaign_type": "ooh",
                "start_date": "2026-03-15T00:00:00",
                "end_date": "2026-04-15T00:00:00"
            }
            
            response = await client.post("/api/campaigns", json=campaign_data, headers=headers)
            log_test("Create campaign", response.status_code == 201)
            
            if response.status_code == 201:
                campaign = response.json()
                test_data['campaign_id'] = campaign['campaign_id']
                test_data['campaign_code'] = campaign['campaign_code']
                
                # List campaigns
                response = await client.get("/api/campaigns", headers=headers)
                log_test("List campaigns", response.status_code == 200)
                
                # Get campaign
                response = await client.get(
                    f"/api/campaigns/{campaign['campaign_id']}", 
                    headers=headers
                )
                log_test("Get campaign by ID", response.status_code == 200)
                
                return True
            
            return False
        
        except Exception as e:
            log_test("Campaign management test", False, str(e))
            return False



async def test_tenant_isolation():
    """Test 6: Verify tenant data isolation."""
    print_section("TEST 6: Tenant Data Isolation")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            # Create second tenant
            tenant2_data = {
                "tenant_name": "Isolated Tenant",
                "subdomain": f"isolated{uuid4().hex[:8]}"
            }
            
            response = await client.post("/api/admin/tenants", json=tenant2_data)
            log_test("Create second tenant", response.status_code == 201)
            
            if response.status_code != 201:
                return False
            
            tenant2 = response.json()
            tenant2_id = tenant2['tenant_id']
            
            # Register client in tenant 2
            client2_data = {
                "email": f"isolated_{uuid4().hex[:8]}@example.com",
                "password": "Test123!@#",
                "company_name": "Isolated Company",
                "phone_number": "+9999999999"
            }
            
            headers2 = {"X-Tenant-ID": tenant2_id}
            response = await client.post("/api/auth/register", json=client2_data, headers=headers2)
            log_test("Register client in tenant 2", response.status_code == 201)
            
            if response.status_code != 201:
                return False
            
            # Login to tenant 2
            login2_data = {
                "email": client2_data['email'],
                "password": client2_data['password']
            }
            
            response = await client.post("/api/auth/login", json=login2_data, headers=headers2)
            log_test("Login to tenant 2", response.status_code == 200)
            
            if response.status_code != 200:
                return False
            
            token2 = response.json()['access_token']
            auth_headers2 = {
                "Authorization": f"Bearer {token2}",
                "X-Tenant-ID": tenant2_id
            }
            
            # Try to access tenant 1's vendors from tenant 2
            response = await client.get("/api/vendors", headers=auth_headers2)
            
            if response.status_code == 200:
                vendors = response.json().get('vendors', [])
                log_test("Tenant 2 cannot see tenant 1 vendors", 
                        len(vendors) == 0,
                        f"Expected 0 vendors, got {len(vendors)}")
            
            # Try to access tenant 1's campaigns from tenant 2
            response = await client.get("/api/campaigns", headers=auth_headers2)
            
            if response.status_code == 200:
                campaigns = response.json().get('campaigns', [])
                log_test("Tenant 2 cannot see tenant 1 campaigns",
                        len(campaigns) == 0,
                        f"Expected 0 campaigns, got {len(campaigns)}")
            
            return True
        
        except Exception as e:
            log_test("Tenant isolation test", False, str(e))
            return False



async def test_branding_api():
    """Test 7: Branding API for frontend."""
    print_section("TEST 7: Branding API")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            tenant_id = test_data.get('test_tenant_id') or test_data.get('default_tenant_id')
            headers = {"X-Tenant-ID": tenant_id}
            
            # Get branding
            response = await client.get("/api/branding", headers=headers)
            log_test("Get branding", response.status_code == 200)
            
            if response.status_code == 200:
                branding = response.json()
                log_test("Branding has tenant_name", 'tenant_name' in branding)
                log_test("Branding has primary_color", 'primary_color' in branding)
                log_test("Branding has secondary_color", 'secondary_color' in branding)
                log_test("Branding has logo_url", 'logo_url' in branding)
                
                # Test without tenant header (should return default)
                response = await client.get("/api/branding")
                log_test("Branding works without tenant header", response.status_code == 200)
                
                return True
            
            return False
        
        except Exception as e:
            log_test("Branding API test", False, str(e))
            return False


async def test_subscription_management():
    """Test 8: Subscription management."""
    print_section("TEST 8: Subscription Management")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            tenant_id = test_data.get('test_tenant_id') or test_data.get('default_tenant_id')
            token = test_data.get('access_token')

            if not token:
                log_test("Subscription test", False, "No access token")
                return False

            headers = {
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": tenant_id
            }

            # Get subscription
            response = await client.get("/api/subscriptions/current", headers=headers)
            log_test("Get subscription", response.status_code == 200)

            if response.status_code == 200:
                subscription = response.json()
                log_test("Subscription has tier", 'tier' in subscription)
                log_test("Subscription has quotas", 'photos_quota' in subscription)

                return True

            return False

        except Exception as e:
            log_test("Subscription test", False, str(e))
            return False





async def test_email_templates():
    """Test 9: Email template system."""
    print_section("TEST 9: Email Template System")
    
    try:
        # Import after ensuring we're in the right directory
        sys.path.insert(0, '/home/lynksavvy/projects/trustcapture/backend')
        
        from app.services.email_template_service import EmailTemplateService, DEFAULT_TEMPLATES
        from app.core.database import AsyncSessionLocal
        
        tenant_id = test_data.get('test_tenant_id') or test_data.get('default_tenant_id')
        
        if not tenant_id:
            log_test("Email template test", False, "No tenant ID available")
            return False
        
        async with AsyncSessionLocal() as db:
            service = EmailTemplateService(db)
            
            # Get available templates
            templates = await service.get_available_templates()
            log_test("Get available templates", len(templates) > 0)
            log_test("Has welcome_email template", 'welcome_email' in templates)
            log_test("Has password_reset template", 'password_reset' in templates)
            log_test("Has photo_approved template", 'photo_approved' in templates)
            log_test("Has photo_rejected template", 'photo_rejected' in templates)
            log_test("Has subscription_expiring template", 'subscription_expiring' in templates)
            
            # Render template
            variables = {
                "user_name": "Test User",
                "user_email": "test@example.com",
                "login_url": "https://app.trustcapture.com/login"
            }
            
            rendered = await service.render_template(
                tenant_id=tenant_id,
                template_name="welcome_email",
                variables=variables,
                format="both"
            )
            
            log_test("Render template", 'subject' in rendered)
            log_test("Template has HTML body", 'html_body' in rendered)
            log_test("Template has text body", 'text_body' in rendered)
            log_test("Variables substituted", 'Test User' in rendered['html_body'])
            
            # Validate template
            valid_template = {
                "subject": "Test",
                "html_body": "<p>Test</p>",
                "text_body": "Test"
            }
            is_valid, error = await service.validate_template(valid_template)
            log_test("Validate valid template", is_valid)
            
            return True
    
    except Exception as e:
        log_test("Email template test", False, str(e))
        return False



async def test_api_health():
    """Test 10: API health and basic endpoints."""
    print_section("TEST 10: API Health Check")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            # Health check
            response = await client.get("/health")
            log_test("Health endpoint", response.status_code == 200)
            
            # Root endpoint
            response = await client.get("/")
            log_test("Root endpoint", response.status_code == 200)
            
            # API docs
            response = await client.get("/api/docs")
            log_test("API docs accessible", response.status_code == 200)
            
            return True
        
        except Exception as e:
            log_test("API health test", False, str(e))
            return False


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("COMPREHENSIVE CHECKPOINT TEST SUITE")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base URL: {BASE_URL}")
    print(f"Database: {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print("\nTesting Phase 1: Backend Multi-Tenancy Implementation")
    print("- Database schema with tenant_config and tenant_id columns")
    print("- Tenant management API (CRUD)")
    print("- Authentication with tenant context")
    print("- Vendor management with tenant isolation")
    print("- Campaign management with tenant isolation")
    print("- Tenant data isolation verification")
    print("- Branding API for frontend")
    print("- Subscription management")
    print("- Email template system")
    print("- API health checks")
    
    # Run tests
    await test_database_schema()
    await test_tenant_management()
    await test_auth_flow()
    await test_vendor_management()
    await test_campaign_management()
    await test_tenant_isolation()
    await test_branding_api()
    await test_subscription_management()
    await test_email_templates()
    await test_api_health()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, p, _ in test_results if p)
    failed = sum(1 for _, p, _ in test_results if not p)
    total = len(test_results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")
    
    if failed > 0:
        print("\n" + "="*80)
        print("FAILED TESTS")
        print("="*80)
        for name, passed, message in test_results:
            if not passed:
                print(f"\n✗ {name}")
                if message:
                    print(f"  Error: {message}")
    
    print("\n" + "="*80)
    print("TEST DATA COLLECTED")
    print("="*80)
    for key, value in test_data.items():
        if 'password' not in key.lower() and 'token' not in key.lower():
            print(f"{key}: {value}")
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
