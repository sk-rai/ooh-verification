# Implementation Plan: Multi-Tenancy and White-Label Architecture

## Overview

This implementation plan transforms the TrustCapture system into a multi-tenant, white-label platform. The approach follows a phased rollout:

1. Backend multi-tenancy foundation (tenant isolation, context, database)
2. Frontend dynamic theming (runtime theme switching, tenant-specific branding)
3. Android white-label support (build variants, flavor-specific resources)
4. Deployment automation (Docker, Terraform, CI/CD for multi-tenant deployments)

The implementation uses:
- **Backend**: Python (FastAPI) with PostgreSQL
- **Frontend**: TypeScript/React with Vite
- **Android**: Kotlin with Gradle build variants
- **Infrastructure**: Docker, Terraform, AWS

All tasks reference specific requirements and include property-based tests to validate correctness properties from the design document.

---

## Phase 1: Backend Multi-Tenancy Foundation

### 1. Database Schema and Tenant Configuration

- [ ] 1.1 Create tenant_config table and migration
  - Create Alembic migration for tenant_config table with columns: tenant_id (PK), tenant_name, subdomain, custom_domain, logo_url, primary_color, secondary_color, email_from_name, email_from_address, email_templates (JSONB), is_active, created_at, updated_at
  - Add unique constraints on subdomain and custom_domain
  - Add indexes on subdomain, custom_domain, and is_active columns
  - _Requirements: 1.1, 1.2, 2.1, 2.2_

- [ ]* 1.2 Write property test for tenant configuration
  - **Property 1: Tenant isolation - No data leakage between tenants**
  - **Validates: Requirements 1.1, 1.3**
  - Use hypothesis to generate random tenant IDs and verify queries never return data from other tenants

- [ ] 1.3 Add tenant_id foreign key to existing tables
  - Create migration to add tenant_id column to: users, vendors, campaigns, photos, audit_logs, subscriptions
  - Add foreign key constraints referencing tenant_config(tenant_id)
  - Add composite indexes on (tenant_id, id) for all tables
  - Set default tenant_id for existing data (migration data backfill)
  - _Requirements: 1.1, 1.3_

- [ ]* 1.4 Write property test for tenant data isolation
  - **Property 2: Query filtering - All queries automatically filter by tenant_id**
  - **Validates: Requirements 1.3**
  - Test that SQLAlchemy queries include tenant_id filter in WHERE clause

### 2. Tenant Context Middleware

- [ ] 2.1 Implement tenant resolution middleware
  - Create `backend/app/middleware/tenant_context.py`
  - Implement TenantContextMiddleware that extracts tenant from: subdomain (tenant.trustcapture.com), custom domain (client.com), or X-Tenant-ID header
  - Store resolved tenant_id in request.state.tenant_id
  - Return 404 if tenant not found or inactive
  - _Requirements: 1.2, 1.4_

- [ ] 2.2 Create tenant context manager for database queries
  - Create `backend/app/core/tenant_context.py` with get_current_tenant() function
  - Implement SQLAlchemy event listeners to automatically inject tenant_id filter
  - Add tenant_id to all ORM queries using query.filter(Model.tenant_id == get_current_tenant())
  - _Requirements: 1.3, 1.4_

- [ ]* 2.3 Write property test for tenant context propagation
  - **Property 3: Context propagation - Tenant context propagates through all layers**
  - **Validates: Requirements 1.4**
  - Test that tenant_id is accessible in routes, services, and database queries

- [ ] 2.4 Update all existing API routes to use tenant context
  - Modify routes in: auth, vendors, campaigns, photos, reports, subscriptions
  - Replace hardcoded queries with tenant-aware queries using get_current_tenant()
  - Add tenant_id to all INSERT operations
  - _Requirements: 1.3, 1.4_

- [ ]* 2.5 Write integration tests for tenant isolation
  - Test creating resources for tenant A and verifying tenant B cannot access them
  - Test API endpoints with different tenant headers/subdomains
  - _Requirements: 1.1, 1.3, 1.4_

### 3. Tenant Management API

- [ ] 3.1 Create tenant CRUD endpoints
  - Create `backend/app/routers/tenants.py`
  - Implement POST /api/admin/tenants (create tenant)
  - Implement GET /api/admin/tenants (list all tenants, admin only)
  - Implement GET /api/admin/tenants/{tenant_id} (get tenant details)
  - Implement PUT /api/admin/tenants/{tenant_id} (update tenant config)
  - Implement DELETE /api/admin/tenants/{tenant_id} (soft delete - set is_active=false)
  - _Requirements: 1.1, 1.2, 2.1_

- [ ] 3.2 Implement tenant branding retrieval endpoint
  - Implement GET /api/branding (public endpoint, no auth required)
  - Return tenant-specific branding: logo_url, primary_color, secondary_color, tenant_name
  - Cache branding data with Redis (5-minute TTL)
  - _Requirements: 2.1, 2.2, 2.3_

- [ ]* 3.3 Write property test for tenant CRUD operations
  - **Property 5: CRUD consistency - Create-read-update-delete operations maintain data consistency**
  - **Validates: Requirements 1.1, 1.2**

- [ ]* 3.4 Write unit tests for tenant API endpoints
  - Test tenant creation with valid/invalid data
  - Test tenant retrieval with different authentication levels
  - Test branding endpoint with subdomain/custom domain resolution
  - _Requirements: 1.1, 1.2, 2.1_

### 4. Email Template System

- [ ] 4.1 Create email template models and storage
  - Add email_templates JSONB column to tenant_config (already in migration 1.1)
  - Define template schema: {template_name: {subject, html_body, text_body, variables}}
  - Create default templates: welcome_email, password_reset, photo_approved, photo_rejected, subscription_expiring
  - _Requirements: 2.4, 2.5_

- [ ] 4.2 Implement email template rendering service
  - Create `backend/app/services/email_template_service.py`
  - Implement render_template(tenant_id, template_name, variables) function
  - Use Jinja2 for variable substitution in templates
  - Support tenant-specific overrides (check tenant_config.email_templates first, fall back to defaults)
  - _Requirements: 2.4, 2.5_

- [ ] 4.3 Update email sending service to use templates
  - Modify `backend/app/services/email_service.py`
  - Replace hardcoded email content with template rendering
  - Use tenant-specific from_name and from_address from tenant_config
  - _Requirements: 2.4, 2.5_

- [ ]* 4.4 Write property test for email template rendering
  - **Property 8: Template rendering - All variables are substituted correctly**
  - **Validates: Requirements 2.4**
  - Generate random template variables and verify they appear in rendered output

- [ ]* 4.5 Write unit tests for email template service
  - Test template rendering with various variable combinations
  - Test tenant-specific template overrides
  - Test fallback to default templates
  - _Requirements: 2.4, 2.5_

### 5. Checkpoint - Backend Multi-Tenancy Validation

- [ ] 5.1 Run all backend tests and verify tenant isolation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify no cross-tenant data leakage in test scenarios
  - Check that all API endpoints respect tenant context

---

## Phase 2: Frontend Dynamic Theming

### 6. Theme Provider and Context

- [ ] 6.1 Create theme context and provider
  - Create `web/src/contexts/ThemeContext.tsx`
  - Define ThemeConfig interface: {primaryColor, secondaryColor, logoUrl, tenantName}
  - Implement ThemeProvider component that fetches branding from /api/branding on mount
  - Store theme in React context and localStorage for persistence
  - _Requirements: 2.2, 2.3, 3.1_

- [ ] 6.2 Implement dynamic CSS variable injection
  - Create `web/src/utils/themeUtils.ts`
  - Implement applyTheme(themeConfig) function that sets CSS custom properties: --primary-color, --secondary-color, --logo-url
  - Update Tailwind config to use CSS variables for primary/secondary colors
  - _Requirements: 2.3, 3.1_

- [ ]* 6.3 Write unit tests for theme provider
  - Test theme fetching and context propagation
  - Test CSS variable injection
  - Test localStorage persistence
  - _Requirements: 2.2, 2.3, 3.1_

### 7. Component Updates for Dynamic Theming

- [ ] 7.1 Update Navigation component with dynamic logo
  - Modify `web/src/components/Navigation.tsx`
  - Replace hardcoded logo with theme.logoUrl from ThemeContext
  - Add fallback to default logo if logoUrl is null
  - _Requirements: 2.2, 3.1_

- [ ] 7.2 Update button and UI components to use theme colors
  - Update button classes to use bg-primary and bg-secondary Tailwind classes
  - Update charts to use theme colors from ThemeContext
  - Update form inputs to use theme colors for focus states
  - _Requirements: 2.3, 3.1_

- [ ] 7.3 Create tenant-specific login page branding
  - Modify `web/src/pages/auth/Login.tsx`
  - Display tenant logo and name on login page
  - Apply theme colors to login form
  - _Requirements: 2.2, 2.3, 3.1_

- [ ]* 7.4 Write integration tests for themed components
  - Test components render with different theme configurations
  - Test theme switching updates all components
  - _Requirements: 2.3, 3.1_

### 8. Subdomain and Custom Domain Handling

- [ ] 8.1 Implement subdomain detection in frontend
  - Create `web/src/utils/tenantUtils.ts`
  - Implement getTenantFromHostname() function that extracts subdomain or custom domain
  - Pass tenant identifier to /api/branding endpoint
  - _Requirements: 1.2, 2.1_

- [ ] 8.2 Configure Vite for multi-tenant development
  - Update `web/vite.config.ts` to support subdomain testing (e.g., tenant1.localhost:5173)
  - Add proxy configuration for tenant-specific API calls
  - _Requirements: 1.2_

- [ ]* 8.3 Write unit tests for tenant detection
  - Test subdomain extraction from various hostname formats
  - Test custom domain detection
  - _Requirements: 1.2_

### 9. Checkpoint - Frontend Theming Validation

- [ ] 9.1 Test frontend with multiple tenant configurations
  - Ensure all tests pass, ask the user if questions arise.
  - Verify theme switching works correctly
  - Test with different subdomain/custom domain configurations

---

## Phase 3: Android White-Label Support

### 10. Gradle Build Variants and Product Flavors

- [ ] 10.1 Configure Gradle product flavors
  - Modify `app/build.gradle.kts` (or `app/build.gradle`)
  - Define product flavors: default, client1, client2 (examples)
  - Configure flavor-specific applicationId: com.trustcapture, com.trustcapture.client1, com.trustcapture.client2
  - Set flavor-specific versionName and versionCode strategies
  - _Requirements: 3.2, 3.3, 3.4_

- [ ] 10.2 Create flavor-specific resource directories
  - Create directory structure: app/src/default/, app/src/client1/, app/src/client2/
  - Create res/ subdirectories for each flavor: values/, drawable/, mipmap/
  - _Requirements: 3.2, 3.3_

- [ ]* 10.3 Write build validation tests
  - Test that each flavor builds successfully
  - Test that flavor-specific resources are included in APK
  - _Requirements: 3.2, 3.3_

### 11. Flavor-Specific Branding Resources

- [ ] 11.1 Implement flavor-specific app names and icons
  - Create app/src/{flavor}/res/values/strings.xml with flavor-specific app_name
  - Add flavor-specific launcher icons to app/src/{flavor}/res/mipmap-*/
  - Add flavor-specific splash screen logos
  - _Requirements: 3.2, 3.3_

- [ ] 11.2 Implement flavor-specific color schemes
  - Create app/src/{flavor}/res/values/colors.xml with primary, secondary, accent colors
  - Update theme definitions to reference flavor-specific colors
  - _Requirements: 3.2, 3.3_

- [ ] 11.3 Create build configuration file for tenant mapping
  - Create `app/tenant_config.json` mapping flavor names to tenant_ids
  - Implement build script to inject tenant_id into BuildConfig
  - _Requirements: 3.2, 3.4_

- [ ]* 11.4 Write property test for flavor resource isolation
  - **Property 15: Flavor isolation - Each flavor uses only its own resources**
  - **Validates: Requirements 3.2, 3.3**
  - Test that APKs contain correct flavor-specific resources

### 12. Runtime Tenant Configuration in Android

- [ ] 12.1 Create TenantConfig singleton in Android
  - Create `app/src/main/java/com/trustcapture/core/TenantConfig.kt`
  - Implement singleton that reads tenant_id from BuildConfig
  - Provide methods: getTenantId(), getApiBaseUrl(), getBrandingConfig()
  - _Requirements: 3.4, 3.5_

- [ ] 12.2 Update API client to include tenant context
  - Modify Retrofit/OkHttp client to add X-Tenant-ID header
  - Use TenantConfig.getTenantId() for header value
  - _Requirements: 1.4, 3.4_

- [ ] 12.3 Implement dynamic branding fetch in Android
  - Create BrandingRepository that fetches /api/branding on app launch
  - Cache branding data in SharedPreferences
  - Update UI components to use cached branding (logo, colors)
  - _Requirements: 2.1, 2.2, 3.5_

- [ ]* 12.4 Write unit tests for TenantConfig
  - Test tenant_id retrieval from BuildConfig
  - Test API header injection
  - _Requirements: 3.4, 3.5_

- [ ]* 12.5 Write integration tests for Android branding
  - Test branding fetch and caching
  - Test UI updates with different branding configurations
  - _Requirements: 2.1, 2.2, 3.5_

### 13. Checkpoint - Android White-Label Validation

- [ ] 13.1 Build and test multiple Android flavors
  - Ensure all tests pass, ask the user if questions arise.
  - Verify each flavor has correct branding and tenant_id
  - Test API calls include correct tenant context

---

## Phase 4: Deployment and Automation

### 14. Docker Multi-Tenant Configuration

- [ ] 14.1 Update Docker Compose for multi-tenancy
  - Modify `docker-compose.yml` to support multiple tenant configurations
  - Add environment variables: TENANT_ID, TENANT_SUBDOMAIN, TENANT_CUSTOM_DOMAIN
  - Configure Nginx reverse proxy for subdomain routing
  - _Requirements: 4.1, 4.2_

- [ ] 14.2 Create tenant-specific Docker Compose overrides
  - Create `docker-compose.tenant1.yml`, `docker-compose.tenant2.yml` examples
  - Configure tenant-specific environment variables and volumes
  - _Requirements: 4.1, 4.2_

- [ ]* 14.3 Write Docker deployment tests
  - Test multi-tenant Docker Compose setup
  - Verify subdomain routing works correctly
  - _Requirements: 4.1, 4.2_

### 15. Terraform Infrastructure as Code

- [ ] 15.1 Create Terraform modules for multi-tenant infrastructure
  - Create `terraform/modules/tenant/` directory
  - Define tenant module with: RDS instance, S3 bucket, CloudFront distribution, Route53 records
  - Parameterize tenant_id, subdomain, custom_domain
  - _Requirements: 4.2, 4.3_

- [ ] 15.2 Implement Terraform workspace strategy
  - Configure Terraform workspaces for: dev, staging, production
  - Create tenant-specific tfvars files: tenant1.tfvars, tenant2.tfvars
  - _Requirements: 4.2, 4.3_

- [ ] 15.3 Create Terraform scripts for tenant provisioning
  - Create `terraform/scripts/provision_tenant.sh` script
  - Automate: create workspace, apply tenant module, output tenant URLs
  - _Requirements: 4.2, 4.3_

- [ ]* 15.4 Write Terraform validation tests
  - Test Terraform plan for tenant module
  - Verify resource naming and tagging conventions
  - _Requirements: 4.2, 4.3_

### 16. CI/CD Pipeline for Multi-Tenant Deployments

- [ ] 16.1 Update CI/CD pipeline for backend multi-tenancy
  - Modify `.github/workflows/backend.yml` (or equivalent)
  - Add tenant-specific deployment stages
  - Configure environment-specific tenant configurations
  - _Requirements: 4.3, 4.4_

- [ ] 16.2 Create CI/CD pipeline for Android flavor builds
  - Create `.github/workflows/android.yml`
  - Build all flavors in parallel
  - Upload flavor-specific APKs to artifact storage
  - _Requirements: 3.3, 4.3, 4.4_

- [ ] 16.3 Implement automated tenant onboarding workflow
  - Create GitHub Actions workflow: `tenant_onboarding.yml`
  - Automate: create tenant in database, provision infrastructure, deploy configuration
  - Trigger workflow with repository dispatch event
  - _Requirements: 4.2, 4.3, 4.4_

- [ ]* 16.4 Write CI/CD pipeline tests
  - Test pipeline runs successfully for each tenant
  - Verify deployments to correct environments
  - _Requirements: 4.3, 4.4_

### 17. Monitoring and Observability

- [ ] 17.1 Implement tenant-specific logging
  - Update logging configuration to include tenant_id in all log entries
  - Configure log aggregation with tenant_id as indexed field
  - _Requirements: 4.5_

- [ ] 17.2 Create tenant-specific metrics and dashboards
  - Add tenant_id label to Prometheus metrics
  - Create Grafana dashboards with tenant filtering
  - Track per-tenant: request count, error rate, response time, storage usage
  - _Requirements: 4.5_

- [ ] 17.3 Implement tenant-specific alerting
  - Configure alerts for: tenant downtime, high error rate, quota exceeded
  - Route alerts to tenant-specific channels (email, Slack)
  - _Requirements: 4.5_

- [ ]* 17.4 Write monitoring integration tests
  - Test metrics collection with tenant_id labels
  - Verify alerts trigger correctly for tenant-specific issues
  - _Requirements: 4.5_

### 18. Documentation and Runbooks

- [ ] 18.1 Create tenant onboarding documentation
  - Document process: create tenant, configure branding, provision infrastructure, deploy
  - Include examples and screenshots
  - _Requirements: 4.2, 4.3_

- [ ] 18.2 Create Android flavor build documentation
  - Document how to add new flavors
  - Explain resource directory structure and BuildConfig usage
  - _Requirements: 3.2, 3.3_

- [ ] 18.3 Create operational runbooks
  - Document: tenant troubleshooting, scaling procedures, backup/restore per tenant
  - Include common issues and solutions
  - _Requirements: 4.5_

### 19. Final Checkpoint - End-to-End Validation

- [ ] 19.1 Perform end-to-end multi-tenant testing
  - Ensure all tests pass, ask the user if questions arise.
  - Test complete flow: onboard tenant, configure branding, deploy, verify isolation
  - Test with at least 3 different tenant configurations
  - Verify performance with 10+ tenants

---

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Checkpoints ensure incremental validation at phase boundaries
- All code examples should use the existing tech stack: Python/FastAPI, TypeScript/React, Kotlin
- Database migrations should be reversible (include downgrade methods)
- All API changes should maintain backward compatibility where possible
- Security: Ensure tenant_id cannot be spoofed or manipulated by clients
- Performance: Add database indexes on tenant_id for all multi-tenant tables
- Testing: Use separate test databases per tenant for integration tests
