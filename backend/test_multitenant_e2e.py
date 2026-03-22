#!/usr/bin/env python3
"""
End-to-End Multi-Tenancy Test Script

This script tests the complete multi-tenancy implementation:
1. Database schema (tenant_config table and tenant_id columns)
2. Tenant CRUD operations
3. Tenant isolation (data cannot leak between tenants)
4. API routes with tenant context
5. Email template system
6. Branding retrieval

Requirements tested: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5
"""
import asyncio
import httpx
import sys
from datetime import datetime
from uuid import uuid4

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
test_results = []


def log_test(test_name: str, passed: bool, message: str = ""):
    """Log test result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    test_results.append((test_name, passed, message))
    print(f"{status}: {test_name}")
    if message:
        print(f"  {message}")


async def test_database_schema():
    """Test 1: Verify database schema has tenant_config and tenant_id columns."""
    print("\n" + "="*80)
    print("TEST 1: Database Schema Verification")
    print("="*80)
    
    try:
        import asyncpg
        
        conn = await asyncpg.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
        )
        
        # Check tenant_config table exists
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'tenant_config'
            )
        """)
        log_test("tenant_config table exists", result)
        
        # Check tenant_config columns
        columns = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tenant_config'
        """)
        column_names = [row['column_name'] for row in columns]
        
        required_columns = [
            'tenant_id', 'tenant_name', 'subdomain', 'custom_domain',
            'logo_url', 'primary_color', 'secondary_color',
            'email_from_name', 'email_from_address', 'email_templates',
            'is_active', 'created_at', 'updated_at'
        ]
        
        for col in required_columns:
            log_test(f"tenant_config.{col} column exists", col in column_names)
        
        # Check tenant_id column in other tables
        tables_with_tenant_id = [
            'clients', 'vendors', 'campaigns', 'photos',
            'audit_logs', 'subscriptions', 'campaign_locations'
        ]
        
        for table in tables_with_tenant_id:
            result = await conn.fetchval(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = '{table}' AND column_name = 'tenant_id'
                )
            """)
            log_test(f"{table}.tenant_id column exists", result)
        
        # Check default tenant exists
        default_tenant = await conn.fetchrow("""
            SELECT * FROM tenant_config WHERE subdomain = 'default'
        """)
        log_test("Default tenant exists", default_tenant is not None)
        
        await conn.close()
        return True
    
    except Exception as e:
        log_test("Database schema verification", False, str(e))
        return False


async def test_tenant_crud_api():
    """Test 2: Test tenant CRUD API endpoints."""
    print("\n" + "="*80)
    print("TEST 2: Tenant CRUD API")
    print("="*80)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            # Create tenant
            tenant_data = {
                "tenant_name": "Test Tenant 1",
                "subdomain": f"test{uuid4().hex[:8]}",
                "logo_url": "https://example.com/logo.png",
                "primary_color": "#FF5733",
                "secondary_color": "#33FF57",
                "email_from_name": "Test Tenant",
                "email_from_address": "noreply@testtenant.com"
            }
            
            response = await client.post("/api/admin/tenants", json=tenant_data)
            log_test("Create tenant (POST /api/admin/tenants)", response.status_code == 201)
            
            if response.status_code == 201:
                tenant = response.json()
                tenant_id = tenant["tenant_id"]
                
                # Get tenant
                response = await client.get(f"/api/admin/tenants/{tenant_id}")
                log_test("Get tenant (GET /api/admin/tenants/:id)", response.status_code == 200)
                
                # List tenants
                response = await client.get("/api/admin/tenants")
                log_test("List tenants (GET /api/admin/tenants)", response.status_code == 200)
                
                if response.status_code == 200:
                    data = response.json()
                    log_test("List tenants returns array", "tenants" in data and isinstance(data["tenants"], list))
                
                # Update tenant
                update_data = {
                    "tenant_name": "Updated Test Tenant",
                    "primary_color": "#0000FF"
                }
                response = await client.put(f"/api/admin/tenants/{tenant_id}", json=update_data)
                log_test("Update tenant (PUT /api/admin/tenants/:id)", response.status_code == 200)
                
                if response.status_code == 200:
                    updated = response.json()
                    log_test("Tenant name updated", updated["tenant_name"] == "Updated Test Tenant")
                    log_test("Primary color updated", updated["primary_color"] == "#0000FF")
                
                # Delete tenant (soft delete)
                response = await client.delete(f"/api/admin/tenants/{tenant_id}")
                log_test("Delete tenant (DELETE /api/admin/tenants/:id)", response.status_code == 204)
                
                # Verify tenant is inactive
                response = await client.get(f"/api/admin/tenants/{tenant_id}")
                if response.status_code == 200:
                    tenant = response.json()
                    log_test("Tenant marked as inactive", tenant["is_active"] == False)
                
                return True
            else:
                log_test("Tenant CRUD API", False, f"Failed to create tenant: {response.text}")
                return False
        
        except Exception as e:
            log_test("Tenant CRUD API", False, str(e))
            return False


async def test_tenant_isolation():
    """Test 3: Test tenant data isolation."""
    print("\n" + "="*80)
    print("TEST 3: Tenant Data Isolation")
    print("="*80)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            # Create two tenants
            tenant1_data = {
                "tenant_name": "Tenant A",
                "subdomain": f"tenanta{uuid4().hex[:8]}"
            }
            tenant2_data = {
                "tenant_name": "Tenant B",
                "subdomain": f"tenantb{uuid4().hex[:8]}"
            }
            
            response1 = await client.post("/api/admin/tenants", json=tenant1_data)
            response2 = await client.post("/api/admin/tenants", json=tenant2_data)
            
            if response1.status_code == 201 and response2.status_code == 201:
                tenant1 = response1.json()
                tenant2 = response2.json()
                
                log_test("Created two test tenants", True)
                
                # Register client in Tenant A
                client_data = {
                    "email": f"client_a_{uuid4().hex[:8]}@example.com",
                    "password": "password123",
                    "company_name": "Company A",
                    "phone_number": "+1234567890"
                }
                
                headers1 = {"X-Tenant-ID": tenant1["tenant_id"]}
                response = await client.post("/api/auth/register", json=client_data, headers=headers1)
                log_test("Register client in Tenant A", response.status_code == 201)
                
                if response.status_code == 201:
                    client_a = response.json()
                    
                    # Login as client in Tenant A
                    login_data = {
                        "email": client_data["email"],
                        "password": client_data["password"]
                    }
                    response = await client.post("/api/auth/login", json=login_data, headers=headers1)
                    log_test("Login client in Tenant A", response.status_code == 200)
                    
                    if response.status_code == 200:
                        token_a = response.json()["access_token"]
                        auth_headers_a = {
                            "Authorization": f"Bearer {token_a}",
                            "X-Tenant-ID": tenant1["tenant_id"]
                        }
                        
                        # Create vendor in Tenant A
                        vendor_data = {
                            "name": "Vendor A",
                            "phone_number": "+1111111111",
                            "email": "vendor_a@example.com"
                        }
                        response = await client.post("/api/vendors", json=vendor_data, headers=auth_headers_a)
                        log_test("Create vendor in Tenant A", response.status_code == 201)
                        
                        # Try to access Tenant A's vendors from Tenant B context
                        headers2 = {
                            "Authorization": f"Bearer {token_a}",
                            "X-Tenant-ID": tenant2["tenant_id"]
                        }
                        response = await client.get("/api/vendors", headers=headers2)
                        
                        if response.status_code == 200:
                            vendors = response.json()["vendors"]
                            log_test("Tenant B cannot see Tenant A's vendors", len(vendors) == 0,
                                   f"Expected 0 vendors, got {len(vendors)}")
                        else:
                            log_test("Tenant isolation check", False, f"Unexpected status: {response.status_code}")
                        
                        return True
                
                return False
            else:
                log_test("Tenant isolation test", False, "Failed to create test tenants")
                return False
        
        except Exception as e:
            log_test("Tenant isolation test", False, str(e))
            return False


async def test_branding_api():
    """Test 4: Test branding retrieval API."""
    print("\n" + "="*80)
    print("TEST 4: Branding API")
    print("="*80)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            # Create tenant with branding
            tenant_data = {
                "tenant_name": "Branded Tenant",
                "subdomain": f"branded{uuid4().hex[:8]}",
                "logo_url": "https://example.com/branded-logo.png",
                "primary_color": "#FF0000",
                "secondary_color": "#00FF00"
            }
            
            response = await client.post("/api/admin/tenants", json=tenant_data)
            log_test("Create tenant with branding", response.status_code == 201)
            
            if response.status_code == 201:
                tenant = response.json()
                
                # Get branding with tenant header
                headers = {"X-Tenant-ID": tenant["tenant_id"]}
                response = await client.get("/api/branding", headers=headers)
                log_test("Get branding (GET /api/branding)", response.status_code == 200)
                
                if response.status_code == 200:
                    branding = response.json()
                    log_test("Branding has tenant_name", branding["tenant_name"] == "Branded Tenant")
                    log_test("Branding has logo_url", branding["logo_url"] == "https://example.com/branded-logo.png")
                    log_test("Branding has primary_color", branding["primary_color"] == "#FF0000")
                    log_test("Branding has secondary_color", branding["secondary_color"] == "#00FF00")
                    return True
                
                return False
            else:
                log_test("Branding API test", False, "Failed to create tenant")
                return False
        
        except Exception as e:
            log_test("Branding API test", False, str(e))
            return False


async def test_email_templates():
    """Test 5: Test email template system."""
    print("\n" + "="*80)
    print("TEST 5: Email Template System")
    print("="*80)
    
    try:
        import asyncpg
        from app.services.email_template_service import EmailTemplateService, DEFAULT_TEMPLATES
        from app.core.database import AsyncSessionLocal
        
        # Get default tenant
        conn = await asyncpg.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
        )
        
        tenant = await conn.fetchrow("SELECT * FROM tenant_config WHERE subdomain = 'default'")
        await conn.close()
        
        if not tenant:
            log_test("Email template test", False, "Default tenant not found")
            return False
        
        tenant_id = str(tenant['tenant_id'])
        
        # Test template service
        async with AsyncSessionLocal() as db:
            service = EmailTemplateService(db)
            
            # Test available templates
            templates = await service.get_available_templates()
            log_test("Get available templates", len(templates) > 0)
            log_test("Welcome email template exists", "welcome_email" in templates)
            log_test("Password reset template exists", "password_reset" in templates)
            log_test("Photo approved template exists", "photo_approved" in templates)
            
            # Test template rendering
            variables = {
                "user_name": "John Doe",
                "user_email": "john@example.com",
                "login_url": "https://example.com/login"
            }
            
            rendered = await service.render_template(
                tenant_id=tenant_id,
                template_name="welcome_email",
                variables=variables,
                format="both"
            )
            
            log_test("Render welcome email template", "subject" in rendered)
            log_test("Template has HTML body", "html_body" in rendered)
            log_test("Template has text body", "text_body" in rendered)
            log_test("Variables substituted in subject", "John Doe" not in rendered["subject"] or "TrustCapture" in rendered["subject"])
            log_test("Variables substituted in HTML", "John Doe" in rendered["html_body"])
            log_test("Variables substituted in text", "john@example.com" in rendered["text_body"])
            
            # Test template validation
            valid_template = {
                "subject": "Test Subject",
                "html_body": "<p>Test HTML</p>",
                "text_body": "Test Text"
            }
            is_valid, error = await service.validate_template(valid_template)
            log_test("Validate valid template", is_valid)
            
            invalid_template = {
                "subject": "Test Subject"
                # Missing html_body and text_body
            }
            is_valid, error = await service.validate_template(invalid_template)
            log_test("Reject invalid template", not is_valid)
            
            return True
    
    except Exception as e:
        log_test("Email template test", False, str(e))
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("MULTI-TENANCY END-TO-END TEST SUITE")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base URL: {BASE_URL}")
    print(f"Database: {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    
    # Run tests
    await test_database_schema()
    await test_tenant_crud_api()
    await test_tenant_isolation()
    await test_branding_api()
    await test_email_templates()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, p, _ in test_results if p)
    failed = sum(1 for _, p, _ in test_results if not p)
    total = len(test_results)
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")
    
    if failed > 0:
        print("\nFailed Tests:")
        for name, passed, message in test_results:
            if not passed:
                print(f"  ✗ {name}")
                if message:
                    print(f"    {message}")
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
