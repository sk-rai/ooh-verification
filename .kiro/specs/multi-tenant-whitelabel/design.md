# Design Document: Multi-Tenancy and White-Label Architecture

## Overview

This design document specifies the technical architecture for adding multi-tenancy and white-labeling capabilities to TrustCapture. The system will enable verification agencies to use the platform under their own brand while maintaining a single codebase and shared infrastructure.

### Goals

- Enable multiple tenants to use TrustCapture with custom branding (colors, logos, domain names)
- Maintain complete data isolation between tenants for security and privacy
- Support two deployment models: SaaS multi-tenant (shared infrastructure) and dedicated instances (isolated infrastructure)
- Provide dynamic theming for web and Android applications without requiring separate deployments
- Enable tenant self-service for branding management and usage analytics
- Ensure system performance scales efficiently with multiple tenants

### Non-Goals

- iOS white-label support (Android only in this phase)
- Multi-language localization (future enhancement)
- Tenant-specific custom code or plugins
- Cross-tenant data sharing or aggregation

### Key Design Decisions

1. **Database Strategy**: Add `tenant_config` table to existing PostgreSQL database rather than separate databases per tenant
   - Rationale: Simpler operations, easier backups, cost-effective for SaaS model
   - Trade-off: Requires strict row-level security and query filtering

2. **Tenant Identification**: Use JWT token claims as primary method, with custom domain mapping as secondary
   - Rationale: Leverages existing authentication system, supports both authenticated and public endpoints
   - Trade-off: Requires middleware to extract and validate tenant context on every request

3. **Frontend Theming**: React Context API with CSS custom properties for dynamic theming
   - Rationale: Native React pattern, no additional dependencies, supports runtime theme changes
   - Trade-off: Requires careful CSS architecture to avoid specificity conflicts

4. **Android White-Label**: Gradle product flavors for build variants
   - Rationale: Standard Android approach, supports separate Play Store listings
   - Trade-off: Requires build configuration per tenant, longer build times

5. **Caching Strategy**: Redis for branding configuration with tenant-specific keys
   - Rationale: Reduces database load, improves response times for branding API
   - Trade-off: Requires cache invalidation strategy on branding updates

6. **Asset Storage**: S3-compatible object storage for tenant logos and assets
   - Rationale: Scalable, CDN-compatible, supports tenant-specific paths
   - Trade-off: Additional infrastructure dependency

## Architecture

### System Architecture Overview

The multi-tenant architecture supports two deployment models:

**Model 1: SaaS Multi-Tenant (Recommended for Most Clients)**
- Single backend instance serves multiple tenants
- Tenant identification via JWT token or custom domain
- Shared database with tenant_id foreign keys on all tables
- Dynamic branding loaded at runtime
- Cost-effective, centralized management

**Model 2: Dedicated Instance (For Enterprise Clients)**
- Isolated backend, database, and infrastructure per tenant
- Complete data and infrastructure isolation
- Custom domain points to dedicated instance
- Higher cost, maximum security and customization

```mermaid
graph TB
    subgraph "SaaS Multi-Tenant Model"
        A[Custom Domain: verify.agency-a.com] --> LB[Load Balancer]
        B[Custom Domain: verify.agency-b.com] --> LB
        C[JWT Token with tenant_id] --> LB
        LB --> API[FastAPI Backend]
        API --> TM[Tenant Middleware]
        TM --> DB[(PostgreSQL<br/>tenant_config table)]
        TM --> Cache[(Redis Cache<br/>Branding Config)]
        API --> S3[S3 Storage<br/>Tenant Logos]
    end
    
    subgraph "Dedicated Instance Model"
        D[Custom Domain: verify.enterprise.com] --> LB2[Load Balancer]
        LB2 --> API2[FastAPI Backend<br/>Dedicated]
        API2 --> DB2[(PostgreSQL<br/>Dedicated)]
        API2 --> Cache2[(Redis Cache<br/>Dedicated)]
        API2 --> S3_2[S3 Storage<br/>Dedicated Bucket]
    end
```

### Component Architecture

```mermaid
graph LR
    subgraph "Frontend Layer"
        WEB[React Web App]
        ANDROID[Android App]
    end
    
    subgraph "API Layer"
        MIDDLEWARE[Tenant Middleware]
        BRANDING_API[Branding API]
        TENANT_API[Tenant Management API]
        CORE_API[Core APIs]
    end
    
    subgraph "Service Layer"
        TENANT_SVC[Tenant Service]
        BRANDING_SVC[Branding Service]
        EMAIL_SVC[Email Service]
        STORAGE_SVC[Storage Service]
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL)]
        CACHE[(Redis)]
        S3[(S3 Storage)]
    end
    
    WEB --> MIDDLEWARE
    ANDROID --> MIDDLEWARE
    MIDDLEWARE --> BRANDING_API
    MIDDLEWARE --> TENANT_API
    MIDDLEWARE --> CORE_API
    
    BRANDING_API --> BRANDING_SVC
    TENANT_API --> TENANT_SVC
    BRANDING_SVC --> CACHE
    BRANDING_SVC --> DB
    BRANDING_SVC --> S3
    EMAIL_SVC --> BRANDING_SVC
    STORAGE_SVC --> S3
```

## Components and Interfaces

### Backend Components

#### 1. Tenant Middleware

**Purpose**: Identify and validate tenant context for every request

**Location**: `backend/app/core/tenant.py`

**Interface**:
```python
class TenantMiddleware:
    async def __call__(self, request: Request, call_next):
        """
        Extract tenant context from request and attach to request.state
        
        Identification methods (in order of precedence):
        1. JWT token claim: token['tenant_id']
        2. Custom domain mapping: domain -> tenant_id lookup
        3. API key header: X-API-Key -> tenant_id lookup
        
        Returns:
            - 401 if tenant identification fails
            - Proceeds with request.state.tenant_id set
        """
        pass

class TenantContext:
    """Thread-safe tenant context for current request"""
    tenant_id: UUID
    tenant_slug: str
    branding: BrandingConfig
    feature_flags: Dict[str, Any]
```

**Dependencies**:
- `app.models.tenant_config.TenantConfig`
- `app.core.security.decode_jwt`
- `app.services.branding_service.BrandingService`

#### 2. Branding Service

**Purpose**: Manage tenant branding configuration with caching

**Location**: `backend/app/services/branding_service.py`

**Interface**:
```python
class BrandingService:
    def __init__(self, db: Session, cache: Redis):
        pass
    
    async def get_branding(self, tenant_id: UUID) -> BrandingConfig:
        """
        Get branding config with cache-aside pattern
        1. Check Redis cache
        2. If miss, query database
        3. Store in cache with 1-hour TTL
        """
        pass
    
    async def update_branding(self, tenant_id: UUID, config: BrandingUpdate) -> BrandingConfig:
        """
        Update branding and invalidate cache
        """
        pass
    
    async def upload_logo(self, tenant_id: UUID, file: UploadFile) -> str:
        """
        Upload logo to S3 and return URL
        Path: s3://bucket/tenants/{tenant_id}/logo.{ext}
        """
        pass
    
    async def get_branding_by_domain(self, domain: str) -> BrandingConfig:
        """
        Public endpoint: get branding by custom domain
        """
        pass
```

#### 3. Tenant Management Service

**Purpose**: Handle tenant lifecycle operations

**Location**: `backend/app/services/tenant_service.py`

**Interface**:
```python
class TenantService:
    async def create_tenant(self, data: TenantCreate) -> TenantConfig:
        """
        Create new tenant with default branding
        """
        pass
    
    async def get_tenant(self, tenant_id: UUID) -> TenantConfig:
        pass
    
    async def update_feature_flags(self, tenant_id: UUID, flags: Dict[str, Any]) -> TenantConfig:
        pass
    
    async def get_usage_stats(self, tenant_id: UUID, start_date: date, end_date: date) -> UsageStats:
        """
        Aggregate usage metrics for tenant
        """
        pass
    
    async def export_tenant_data(self, tenant_id: UUID, format: str) -> bytes:
        """
        Export all tenant data as JSON or CSV
        """
        pass
```

#### 4. Email Template Service

**Purpose**: Render emails with tenant branding

**Location**: `backend/app/services/email_template_service.py`

**Interface**:
```python
class EmailTemplateService:
    def __init__(self, branding_service: BrandingService):
        pass
    
    async def render_template(
        self, 
        tenant_id: UUID, 
        template_type: EmailType,
        variables: Dict[str, Any]
    ) -> EmailContent:
        """
        Render email template with tenant branding
        
        Template types:
        - VERIFICATION_REQUEST
        - VERIFICATION_COMPLETE
        - PASSWORD_RESET
        - ACCOUNT_CREATED
        
        Injected variables:
        - {{brand_name}}
        - {{logo_url}}
        - {{primary_color}}
        - {{contact_email}}
        - {{support_phone}}
        - + template-specific variables
        """
        pass
```

### API Endpoints

#### Branding Endpoints

```
GET    /api/v1/branding
       Description: Get authenticated tenant's branding
       Auth: Required (JWT)
       Response: BrandingConfig
       
GET    /api/v1/branding/public/{domain}
       Description: Get branding by custom domain (public)
       Auth: None
       Response: BrandingConfig
       
PUT    /api/v1/admin/branding/{tenant_id}
       Description: Update tenant branding (admin only)
       Auth: Required (Admin JWT)
       Body: BrandingUpdate
       Response: BrandingConfig
       
POST   /api/v1/admin/branding/{tenant_id}/logo
       Description: Upload tenant logo (admin only)
       Auth: Required (Admin JWT)
       Body: multipart/form-data (file)
       Response: { logo_url: string }
```

#### Tenant Management Endpoints

```
POST   /api/v1/admin/tenants
       Description: Create new tenant
       Auth: Required (Admin JWT)
       Body: TenantCreate
       Response: TenantConfig
       
GET    /api/v1/admin/tenants/{tenant_id}
       Description: Get tenant details
       Auth: Required (Admin JWT)
       Response: TenantConfig
       
PUT    /api/v1/admin/tenants/{tenant_id}/feature-flags
       Description: Update tenant feature flags
       Auth: Required (Admin JWT)
       Body: { flags: Dict[str, Any] }
       Response: TenantConfig
       
GET    /api/v1/tenant/usage
       Description: Get usage stats for authenticated tenant
       Auth: Required (JWT)
       Query: start_date, end_date
       Response: UsageStats
       
POST   /api/v1/tenant/export
       Description: Export tenant data
       Auth: Required (JWT)
       Body: { format: "json" | "csv" }
       Response: File download
```

### Frontend Components

#### 1. Theme Context Provider

**Purpose**: Provide tenant branding to all React components

**Location**: `web/src/contexts/ThemeContext.tsx`

**Interface**:
```typescript
interface BrandingConfig {
  primaryColor: string;
  secondaryColor: string;
  accentColor: string;
  logoUrl: string;
  brandName: string;
  customDomain?: string;
  contactEmail: string;
  supportPhone: string;
  companyLegalName: string;
}

interface ThemeContextValue {
  branding: BrandingConfig | null;
  loading: boolean;
  error: Error | null;
  refreshBranding: () => Promise<void>;
}

export const ThemeProvider: React.FC<{ children: React.ReactNode }>;
export const useTheme: () => ThemeContextValue;
```

**Behavior**:
- Fetch branding on mount via `/api/v1/branding` or `/api/v1/branding/public/{domain}`
- Apply CSS custom properties to `:root`
- Provide branding to child components via context
- Handle loading and error states

#### 2. Themed Components

**Purpose**: Components that adapt to tenant branding

**Examples**:
- `<Logo />`: Displays tenant logo or default
- `<BrandedButton />`: Uses primary color
- `<Navigation />`: Uses brand name in header
- `<Footer />`: Displays tenant contact info

### Android Components

#### 1. Product Flavors Configuration

**Location**: `app/build.gradle`

**Structure**:
```gradle
android {
    flavorDimensions "tenant"
    
    productFlavors {
        trustcapture {
            dimension "tenant"
            applicationId "com.trustcapture.verify"
            manifestPlaceholders = [
                appName: "TrustCapture",
                appIcon: "@mipmap/ic_launcher_trustcapture"
            ]
            buildConfigField "String", "API_BASE_URL", "\"https://api.trustcapture.com\""
            buildConfigField "String", "TENANT_ID", "\"default\""
        }
        
        clienta {
            dimension "tenant"
            applicationId "com.clienta.verify"
            manifestPlaceholders = [
                appName: "ClientA Verify",
                appIcon: "@mipmap/ic_launcher_clienta"
            ]
            buildConfigField "String", "API_BASE_URL", "\"https://api.trustcapture.com\""
            buildConfigField "String", "TENANT_ID", "\"client-a-uuid\""
        }
    }
}
```

#### 2. Theme Manager

**Purpose**: Load and apply tenant branding in Android app

**Location**: `app/src/main/java/com/trustcapture/theme/ThemeManager.kt`

**Interface**:
```kotlin
class ThemeManager(private val context: Context) {
    suspend fun loadBranding(): BrandingConfig {
        // 1. Check if flavor has API-based theming enabled
        // 2. Fetch from API: /api/v1/branding
        // 3. Cache locally with SharedPreferences
        // 4. Fall back to flavor resources if API fails
    }
    
    fun applyTheme(branding: BrandingConfig) {
        // Apply colors to Material Theme
        // Update app bar colors
        // Update button styles
    }
}

data class BrandingConfig(
    val primaryColor: String,
    val secondaryColor: String,
    val accentColor: String,
    val logoUrl: String,
    val brandName: String
)
```

## Data Models

### Database Schema

#### tenant_config Table

```sql
CREATE TABLE tenant_config (
    tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Branding
    primary_color VARCHAR(7) NOT NULL DEFAULT '#1E40AF',  -- Hex color
    secondary_color VARCHAR(7) NOT NULL DEFAULT '#3B82F6',
    accent_color VARCHAR(7) NOT NULL DEFAULT '#60A5FA',
    logo_url TEXT,
    brand_name VARCHAR(255) NOT NULL,
    
    -- Domain and Contact
    custom_domain VARCHAR(255) UNIQUE,
    contact_email VARCHAR(255) NOT NULL,
    support_phone VARCHAR(20),
    company_legal_name VARCHAR(255) NOT NULL,
    
    -- Feature Flags (JSONB for flexibility)
    feature_flags JSONB NOT NULL DEFAULT '{}',
    
    -- Rate Limiting
    rate_limit_requests_per_minute INTEGER DEFAULT 60,
    rate_limit_verifications_per_day INTEGER DEFAULT 1000,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_primary_color CHECK (primary_color ~ '^#[0-9A-Fa-f]{6}$'),
    CONSTRAINT valid_secondary_color CHECK (secondary_color ~ '^#[0-9A-Fa-f]{6}$'),
    CONSTRAINT valid_accent_color CHECK (accent_color ~ '^#[0-9A-Fa-f]{6}$'),
    CONSTRAINT valid_email CHECK (contact_email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

-- Indexes
CREATE INDEX idx_tenant_config_custom_domain ON tenant_config(custom_domain);
CREATE INDEX idx_tenant_config_brand_name ON tenant_config(brand_name);

-- Trigger for updated_at
CREATE TRIGGER update_tenant_config_updated_at
    BEFORE UPDATE ON tenant_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

#### Linking Existing Tables to Tenants

Add `tenant_id` foreign key to existing tables:

```sql
-- Add tenant_id to clients table
ALTER TABLE clients ADD COLUMN tenant_id UUID REFERENCES tenant_config(tenant_id);
CREATE INDEX idx_clients_tenant_id ON clients(tenant_id);

-- Add tenant_id to vendors table
ALTER TABLE vendors ADD COLUMN tenant_id UUID REFERENCES tenant_config(tenant_id);
CREATE INDEX idx_vendors_tenant_id ON vendors(tenant_id);

-- Add tenant_id to campaigns table
ALTER TABLE campaigns ADD COLUMN tenant_id UUID REFERENCES tenant_config(tenant_id);
CREATE INDEX idx_campaigns_tenant_id ON campaigns(tenant_id);

-- Add tenant_id to photos table
ALTER TABLE photos ADD COLUMN tenant_id UUID REFERENCES tenant_config(tenant_id);
CREATE INDEX idx_photos_tenant_id ON photos(tenant_id);

-- Add tenant_id to audit_logs table
ALTER TABLE audit_logs ADD COLUMN tenant_id UUID REFERENCES tenant_config(tenant_id);
CREATE INDEX idx_audit_logs_tenant_id ON audit_logs(tenant_id);
```

### SQLAlchemy Models

#### TenantConfig Model

**Location**: `backend/app/models/tenant_config.py`

```python
from sqlalchemy import Column, String, Integer, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base

class TenantConfig(Base):
    """
    Tenant configuration model for multi-tenancy and white-labeling.
    
    Validates: Requirements 1, 2
    """
    __tablename__ = "tenant_config"
    
    # Primary Key
    tenant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Branding
    primary_color = Column(String(7), nullable=False, default='#1E40AF')
    secondary_color = Column(String(7), nullable=False, default='#3B82F6')
    accent_color = Column(String(7), nullable=False, default='#60A5FA')
    logo_url = Column(String, nullable=True)
    brand_name = Column(String(255), nullable=False)
    
    # Domain and Contact
    custom_domain = Column(String(255), unique=True, nullable=True)
    contact_email = Column(String(255), nullable=False)
    support_phone = Column(String(20), nullable=True)
    company_legal_name = Column(String(255), nullable=False)
    
    # Feature Flags
    feature_flags = Column(JSONB, nullable=False, default={})
    
    # Rate Limiting
    rate_limit_requests_per_minute = Column(Integer, default=60)
    rate_limit_verifications_per_day = Column(Integer, default=1000)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint("primary_color ~ '^#[0-9A-Fa-f]{6}$'", name='valid_primary_color'),
        CheckConstraint("secondary_color ~ '^#[0-9A-Fa-f]{6}$'", name='valid_secondary_color'),
        CheckConstraint("accent_color ~ '^#[0-9A-Fa-f]{6}$'", name='valid_accent_color'),
        CheckConstraint("contact_email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}$'", name='valid_email'),
    )
    
    def __repr__(self):
        return f"<TenantConfig(tenant_id={self.tenant_id}, brand_name={self.brand_name})>"
```

### Pydantic Schemas

#### Branding Schemas

**Location**: `backend/app/schemas/tenant.py`

```python
from pydantic import BaseModel, Field, validator, HttpUrl, EmailStr
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

class BrandingConfig(BaseModel):
    """Response schema for branding configuration"""
    tenant_id: UUID
    primary_color: str = Field(..., regex=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: str = Field(..., regex=r'^#[0-9A-Fa-f]{6}$')
    accent_color: str = Field(..., regex=r'^#[0-9A-Fa-f]{6}$')
    logo_url: Optional[str] = None
    brand_name: str
    custom_domain: Optional[str] = None
    contact_email: EmailStr
    support_phone: Optional[str] = None
    company_legal_name: str
    
    class Config:
        orm_mode = True

class BrandingUpdate(BaseModel):
    """Request schema for updating branding"""
    primary_color: Optional[str] = Field(None, regex=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, regex=r'^#[0-9A-Fa-f]{6}$')
    accent_color: Optional[str] = Field(None, regex=r'^#[0-9A-Fa-f]{6}$')
    logo_url: Optional[str] = None
    brand_name: Optional[str] = None
    custom_domain: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    support_phone: Optional[str] = None
    company_legal_name: Optional[str] = None

class TenantCreate(BaseModel):
    """Request schema for creating a tenant"""
    brand_name: str
    company_legal_name: str
    contact_email: EmailStr
    support_phone: Optional[str] = None
    custom_domain: Optional[str] = None
    primary_color: str = Field('#1E40AF', regex=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: str = Field('#3B82F6', regex=r'^#[0-9A-Fa-f]{6}$')
    accent_color: str = Field('#60A5FA', regex=r'^#[0-9A-Fa-f]{6}$')
    feature_flags: Dict[str, Any] = Field(default_factory=dict)

class TenantConfigResponse(BaseModel):
    """Response schema for tenant configuration"""
    tenant_id: UUID
    branding: BrandingConfig
    feature_flags: Dict[str, Any]
    rate_limit_requests_per_minute: int
    rate_limit_verifications_per_day: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class UsageStats(BaseModel):
    """Response schema for tenant usage statistics"""
    tenant_id: UUID
    period_start: datetime
    period_end: datetime
    total_api_requests: int
    total_verifications: int
    total_photos_uploaded: int
    total_campaigns: int
    total_vendors: int
    storage_used_bytes: int
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified the following redundancies and consolidations:

**Consolidated Properties:**
- Requirements 1.1-1.9 (storing various branding fields) can be consolidated into a single round-trip property for tenant configuration
- Requirements 2.2-2.4 (boolean, string, numeric feature flags) are all covered by 2.1 (key-value pairs)
- Requirements 5.2-5.5 (injecting various branding elements into emails) can be consolidated into a single property about email template rendering
- Requirements 6.2-6.3 (different types of rate limits) can be consolidated into a single property about rate limit enforcement
- Requirements 7.1-7.2 (logging requests and modifications) can be consolidated into a single property about audit logging
- Requirements 9.2-9.4 (applying colors, logo, brand name) can be consolidated into a single property about UI branding application
- Android build configuration requirements (11.1-11.2, 12.1-12.4, 14.1) are build system tests, not runtime properties

**Eliminated Redundancies:**
- Property 4.10 (return HTTP 200 for successful requests) is implied by other properties that verify correct responses
- Requirements about documentation (3.6, 11.3, 14.2, 16.2) are not testable properties
- Requirements about infrastructure configuration (17.1-17.2, 18.1-18.2, 24.1) are not runtime testable properties

### Property 1: Tenant Configuration Round-Trip

*For any* valid tenant configuration (including all branding fields: colors, logo URL, brand name, custom domain, contact email, support phone, company legal name), creating a tenant and then retrieving it should return an equivalent configuration.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9**

### Property 2: Branding Color Validation

*For any* string that is not a valid hex color code (format: #RRGGBB), attempting to update tenant branding with that color should be rejected with a validation error.

**Validates: Requirements 1.10**

### Property 3: URL Validation

*For any* string that is not a valid HTTP/HTTPS URL, attempting to update tenant branding with that URL as a logo should be rejected with a validation error.

**Validates: Requirements 1.11**

### Property 4: Email Validation

*For any* string that is not a valid email address format, attempting to update tenant branding with that email should be rejected with a validation error.

**Validates: Requirements 1.12**

### Property 5: Feature Flag Round-Trip

*For any* tenant and any valid feature flag configuration (key-value pairs with boolean, string, or numeric values), updating feature flags and then retrieving them should return an equivalent configuration.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

### Property 6: Feature Flag Default Fallback

*For any* tenant and any feature flag key that is not defined for that tenant, querying that feature flag should return the system default value.

**Validates: Requirements 2.5**

### Property 7: Tenant Identification from JWT

*For any* valid JWT token containing a tenant_id claim, the tenant middleware should extract and attach the correct tenant identifier to the request context.

**Validates: Requirements 3.1**

### Property 8: Tenant Identification from Custom Domain

*For any* custom domain that is mapped to a tenant, requests to that domain should be identified as belonging to the correct tenant.

**Validates: Requirements 3.2**

### Property 9: Tenant Identification from API Key

*For any* API key that is mapped to a tenant, requests with that API key should be identified as belonging to the correct tenant.

**Validates: Requirements 3.3**

### Property 10: Tenant Identification Failure Returns 401

*For any* request that does not contain valid tenant identification (no JWT, no custom domain mapping, no API key), the tenant middleware should return HTTP 401 Unauthorized.

**Validates: Requirements 3.4**

### Property 11: Tenant Context Attachment

*For any* valid authenticated request, the tenant middleware should attach tenant context (tenant_id, branding, feature_flags) to the request object for use by downstream handlers.

**Validates: Requirements 3.5**

### Property 12: Tenant Identification Audit Logging

*For any* request processed by the tenant middleware, a log entry should be created containing the tenant identifier and identification method used.

**Validates: Requirements 3.7**

### Property 13: Branding Response Structure

*For any* tenant, the branding API response should contain all required fields: primary_color, secondary_color, accent_color, logo_url, brand_name, custom_domain, contact_email, support_phone, company_legal_name.

**Validates: Requirements 4.3**

### Property 14: Logo File Type Validation

*For any* file that is not an image format (PNG, JPG, SVG), attempting to upload it as a tenant logo should be rejected with a validation error.

**Validates: Requirements 4.7**

### Property 15: Logo File Size Validation

*For any* file larger than 2MB, attempting to upload it as a tenant logo should be rejected with a validation error.

**Validates: Requirements 4.8**

### Property 16: Logo Storage Path

*For any* uploaded tenant logo, the file should be stored in object storage at a tenant-specific path (e.g., s3://bucket/tenants/{tenant_id}/logo.{ext}).

**Validates: Requirements 4.9**

### Property 17: Branding Not Found Returns 404

*For any* request for tenant branding where the tenant does not exist, the API should return HTTP 404.

**Validates: Requirements 4.11**

### Property 18: Email Template Branding Injection

*For any* email sent to a tenant's users, the rendered email should contain the tenant's brand name, brand colors, logo URL, and contact information.

**Validates: Requirements 5.2, 5.3, 5.4, 5.5**

### Property 19: Email Template Variable Substitution

*For any* email template with template variables (e.g., {{user_name}}, {{verification_code}}), rendering the template with variable values should replace all variables with their corresponding values.

**Validates: Requirements 5.6**

### Property 20: Email Template Selection by Tenant

*For any* email sent, the system should select the template based on the tenant context, using the tenant's custom template if available, or the default template with tenant branding if not.

**Validates: Requirements 5.7**

### Property 21: Email Template Validation

*For any* email template that does not contain all required template variables for its type, attempting to save that template should be rejected with a validation error.

**Validates: Requirements 5.10**

### Property 22: Tenant-Specific Rate Limiting

*For any* tenant with configured rate limits, requests from that tenant should be rate limited according to their specific configuration (requests per minute, verifications per day).

**Validates: Requirements 6.1, 6.2, 6.3**

### Property 23: Audit Log Tenant Tagging

*For any* API request or data modification, the audit log entry should include the tenant identifier.

**Validates: Requirements 7.1, 7.2**

### Property 24: Tenant Data Isolation in Queries

*For any* database query executed in a tenant context, the results should only include data belonging to that tenant (filtered by tenant_id).

**Validates: Requirements 8.1**

### Property 25: Cross-Tenant Access Prevention

*For any* API request from tenant A attempting to access data belonging to tenant B, the request should be rejected with an authorization error.

**Validates: Requirements 8.2**

### Property 26: Frontend Branding Application

*For any* tenant branding configuration loaded by the frontend, the UI should reflect the tenant's colors, logo, and brand name in all relevant components.

**Validates: Requirements 9.2, 9.3, 9.4**

### Property 27: CSS Custom Properties Generation

*For any* tenant branding configuration, the frontend should generate CSS custom properties (--primary-color, --secondary-color, --accent-color) that can be used throughout the application.

**Validates: Requirements 9.5**

### Property 28: Custom Domain Mapping

*For any* custom domain mapped to a tenant, requests to that domain should resolve to the correct tenant's branding and data.

**Validates: Requirements 10.1**

### Property 29: Android API Theme Priority

*For any* Android flavor with API-based theming enabled, when both flavor resources and API branding are available, the API branding should take precedence.

**Validates: Requirements 13.3**

### Property 30: Multi-Tenant Support

*For any* set of multiple tenants in a single deployment, each tenant should be able to operate independently with their own branding, data, and configuration without interference.

**Validates: Requirements 15.1**

### Property 31: Frontend Environment Variable Configuration

*For any* environment variable set for the frontend (e.g., API_BASE_URL), the frontend should use that value for its configuration.

**Validates: Requirements 17.3**

### Property 32: Client Portal File Upload Validation

*For any* file upload in the client portal, files that do not meet the validation criteria (file type, file size) should be rejected before upload.

**Validates: Requirements 20.2**

### Property 33: Branding Configuration Caching

*For any* tenant branding configuration, after the first request, subsequent requests should be served from cache (Redis) until the cache expires or is invalidated.

**Validates: Requirements 22.1**

### Property 34: CDN Asset Serving

*For any* static asset (logo, images), the asset should be served from a CDN with a tenant-specific path.

**Validates: Requirements 22.2**

### Property 35: Incremental Data Export

*For any* tenant data export request with a "since" timestamp, the export should only include data created or modified after that timestamp.

**Validates: Requirements 23.2**

### Property 36: Tenant Metrics Collection

*For any* tenant activity (API requests, verifications, photo uploads), metrics should be recorded with the tenant identifier for monitoring and analytics.

**Validates: Requirements 25.1**

### Property 37: Data Encryption at Rest

*For any* tenant data stored in the database, the data should be encrypted at rest using the configured encryption mechanism.

**Validates: Requirements 26.1**

### Property 38: Configuration Parsing Round-Trip

*For any* valid tenant configuration file, parsing the file and then serializing it back should produce an equivalent configuration.

**Validates: Requirements 27.1**

### Property 39: Configuration Schema Validation

*For any* tenant configuration that does not conform to the schema (missing required fields, invalid types, constraint violations), attempting to parse or save that configuration should be rejected with a validation error.

**Validates: Requirements 27.2**

## Error Handling

### Tenant Identification Errors

**Error**: Tenant not found
- **HTTP Status**: 401 Unauthorized
- **Response**: `{"error": "tenant_not_found", "message": "Unable to identify tenant from request"}`
- **Handling**: Log the error, return 401, do not proceed with request

**Error**: Invalid JWT token
- **HTTP Status**: 401 Unauthorized
- **Response**: `{"error": "invalid_token", "message": "JWT token is invalid or expired"}`
- **Handling**: Log the error, return 401, do not proceed with request

**Error**: Custom domain not mapped
- **HTTP Status**: 401 Unauthorized
- **Response**: `{"error": "domain_not_mapped", "message": "Custom domain is not mapped to any tenant"}`
- **Handling**: Log the error, return 401, do not proceed with request

### Branding Configuration Errors

**Error**: Invalid color format
- **HTTP Status**: 422 Unprocessable Entity
- **Response**: `{"error": "validation_error", "field": "primary_color", "message": "Color must be in hex format (#RRGGBB)"}`
- **Handling**: Return validation error, do not save configuration

**Error**: Invalid URL format
- **HTTP Status**: 422 Unprocessable Entity
- **Response**: `{"error": "validation_error", "field": "logo_url", "message": "URL must be a valid HTTP/HTTPS URL"}`
- **Handling**: Return validation error, do not save configuration

**Error**: Invalid email format
- **HTTP Status**: 422 Unprocessable Entity
- **Response**: `{"error": "validation_error", "field": "contact_email", "message": "Email must be a valid email address"}`
- **Handling**: Return validation error, do not save configuration

**Error**: Logo file too large
- **HTTP Status**: 413 Payload Too Large
- **Response**: `{"error": "file_too_large", "message": "Logo file must be less than 2MB"}`
- **Handling**: Return error, do not upload file

**Error**: Invalid logo file type
- **HTTP Status**: 422 Unprocessable Entity
- **Response**: `{"error": "invalid_file_type", "message": "Logo must be PNG, JPG, or SVG format"}`
- **Handling**: Return error, do not upload file

### Data Isolation Errors

**Error**: Cross-tenant access attempt
- **HTTP Status**: 403 Forbidden
- **Response**: `{"error": "access_denied", "message": "You do not have permission to access this resource"}`
- **Handling**: Log security event, return 403, do not return data

**Error**: Tenant data not found
- **HTTP Status**: 404 Not Found
- **Response**: `{"error": "not_found", "message": "Resource not found"}`
- **Handling**: Return 404, do not reveal whether resource exists for another tenant

### Rate Limiting Errors

**Error**: Rate limit exceeded
- **HTTP Status**: 429 Too Many Requests
- **Response**: `{"error": "rate_limit_exceeded", "message": "Rate limit exceeded. Try again in X seconds", "retry_after": X}`
- **Headers**: `Retry-After: X`, `X-RateLimit-Limit: Y`, `X-RateLimit-Remaining: 0`, `X-RateLimit-Reset: timestamp`
- **Handling**: Return 429, include retry information, do not process request

### Configuration Errors

**Error**: Invalid configuration schema
- **HTTP Status**: 422 Unprocessable Entity
- **Response**: `{"error": "validation_error", "message": "Configuration does not match schema", "details": [...]}`
- **Handling**: Return validation errors, do not save configuration

**Error**: Missing required configuration field
- **HTTP Status**: 422 Unprocessable Entity
- **Response**: `{"error": "validation_error", "field": "brand_name", "message": "Field is required"}`
- **Handling**: Return validation error, do not save configuration

### Storage Errors

**Error**: S3 upload failure
- **HTTP Status**: 500 Internal Server Error
- **Response**: `{"error": "storage_error", "message": "Failed to upload file to storage"}`
- **Handling**: Log error with details, return 500, retry with exponential backoff

**Error**: S3 access denied
- **HTTP Status**: 500 Internal Server Error
- **Response**: `{"error": "storage_error", "message": "Storage access denied"}`
- **Handling**: Log error, alert operations team, return 500

### Cache Errors

**Error**: Redis connection failure
- **HTTP Status**: N/A (transparent fallback)
- **Handling**: Log warning, fall back to database query, continue request processing

**Error**: Cache deserialization error
- **HTTP Status**: N/A (transparent fallback)
- **Handling**: Log error, invalidate cache entry, fall back to database query

## Testing Strategy

### Dual Testing Approach

This feature requires both unit testing and property-based testing for comprehensive coverage:

**Unit Tests**: Focus on specific examples, edge cases, and integration points
- Specific branding configurations (default colors, custom colors)
- Tenant identification methods (JWT, custom domain, API key)
- Email template rendering for each email type
- Error conditions (invalid inputs, missing data)
- Integration between components (middleware → service → database)

**Property-Based Tests**: Verify universal properties across all inputs
- Configuration round-trip properties (create → retrieve → verify)
- Validation properties (reject all invalid inputs)
- Data isolation properties (tenant A cannot access tenant B's data)
- Rate limiting properties (enforce limits for all tenants)
- Branding application properties (all UI components reflect tenant branding)

### Property-Based Testing Configuration

**Library Selection**: 
- Backend (Python): Use `hypothesis` library for property-based testing
- Frontend (TypeScript): Use `fast-check` library for property-based testing
- Android (Kotlin): Use `kotest-property` library for property-based testing

**Test Configuration**:
- Minimum 100 iterations per property test (due to randomization)
- Each property test must reference its design document property
- Tag format: `# Feature: multi-tenant-whitelabel, Property {number}: {property_text}`

**Example Property Test Structure** (Python/Hypothesis):

```python
from hypothesis import given, strategies as st
import pytest

# Feature: multi-tenant-whitelabel, Property 1: Tenant Configuration Round-Trip
@given(
    primary_color=st.from_regex(r'^#[0-9A-Fa-f]{6}$'),
    secondary_color=st.from_regex(r'^#[0-9A-Fa-f]{6}$'),
    accent_color=st.from_regex(r'^#[0-9A-Fa-f]{6}$'),
    brand_name=st.text(min_size=1, max_size=255),
    contact_email=st.emails(),
    company_legal_name=st.text(min_size=1, max_size=255)
)
@pytest.mark.property_test
def test_tenant_configuration_round_trip(
    primary_color, secondary_color, accent_color, 
    brand_name, contact_email, company_legal_name
):
    """
    Property 1: For any valid tenant configuration, creating a tenant 
    and then retrieving it should return an equivalent configuration.
    """
    # Create tenant with generated configuration
    tenant_data = TenantCreate(
        primary_color=primary_color,
        secondary_color=secondary_color,
        accent_color=accent_color,
        brand_name=brand_name,
        contact_email=contact_email,
        company_legal_name=company_legal_name
    )
    created_tenant = tenant_service.create_tenant(tenant_data)
    
    # Retrieve tenant
    retrieved_tenant = tenant_service.get_tenant(created_tenant.tenant_id)
    
    # Verify equivalence
    assert retrieved_tenant.primary_color == primary_color
    assert retrieved_tenant.secondary_color == secondary_color
    assert retrieved_tenant.accent_color == accent_color
    assert retrieved_tenant.brand_name == brand_name
    assert retrieved_tenant.contact_email == contact_email
    assert retrieved_tenant.company_legal_name == company_legal_name
```

### Unit Testing Strategy

**Backend Unit Tests**:
- Test each API endpoint with specific examples
- Test middleware with different authentication methods
- Test service layer with mock dependencies
- Test database models with specific data
- Test validation logic with edge cases

**Frontend Unit Tests**:
- Test theme context provider with specific branding configs
- Test themed components with different color schemes
- Test branding API integration with mock responses
- Test error handling for failed branding loads
- Test CSS custom property generation

**Android Unit Tests**:
- Test theme manager with specific branding configs
- Test API branding fetch and cache
- Test flavor precedence logic
- Test Material Theme application

### Integration Testing

**Multi-Tenant Scenarios**:
- Create multiple tenants with different branding
- Verify each tenant sees only their own data
- Verify branding is applied correctly for each tenant
- Verify rate limits are enforced independently

**Cross-Tenant Isolation**:
- Attempt to access tenant B's data with tenant A's credentials
- Verify all attempts are rejected with 403 Forbidden
- Verify no data leakage in error messages

**Custom Domain Testing**:
- Map custom domains to tenants
- Verify requests to custom domains are identified correctly
- Verify branding is applied based on domain

**End-to-End Workflows**:
- Tenant onboarding: Create tenant → Upload logo → Configure branding → Verify frontend
- Branding update: Update colors → Verify cache invalidation → Verify frontend reflects changes
- Data export: Create data → Export → Verify export contains only tenant's data

### Performance Testing

**Load Testing**:
- Simulate multiple tenants making concurrent requests
- Verify response times remain acceptable (< 200ms for branding API)
- Verify cache hit rate is high (> 90% for branding requests)

**Scalability Testing**:
- Test with 100+ tenants in single deployment
- Verify database query performance with tenant_id filtering
- Verify Redis cache performance with many tenant keys

**Stress Testing**:
- Test rate limiting under heavy load
- Verify system remains stable when rate limits are exceeded
- Verify error responses are returned quickly

### Security Testing

**Tenant Isolation Testing**:
- Automated tests for every API endpoint to verify tenant isolation
- Attempt SQL injection with tenant_id manipulation
- Attempt JWT token manipulation to access other tenants

**Authentication Testing**:
- Test with invalid JWT tokens
- Test with expired JWT tokens
- Test with missing authentication
- Verify all return 401 Unauthorized

**Authorization Testing**:
- Test admin endpoints with non-admin users
- Test tenant-specific endpoints with wrong tenant credentials
- Verify all return 403 Forbidden

### Deployment Testing

**Multi-Tenant Deployment**:
- Deploy with Docker Compose
- Verify all services start correctly
- Verify tenant isolation in shared deployment
- Verify health check endpoints

**Dedicated Instance Deployment**:
- Deploy dedicated instance with Terraform
- Verify instance is isolated
- Verify custom domain points to dedicated instance
- Verify data is isolated



## Deployment Architecture

### SaaS Multi-Tenant Deployment

**Infrastructure Components**:
- Load Balancer (nginx or cloud load balancer)
- FastAPI Backend (multiple instances for high availability)
- PostgreSQL Database (single instance with tenant_id on all tables)
- Redis Cache (for branding configuration and rate limiting)
- S3-compatible Object Storage (for tenant logos and assets)

**Docker Compose Configuration**:

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
    networks:
      - trustcapture-network

  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/trustcapture
      - REDIS_URL=redis://redis:6379/0
      - S3_BUCKET=trustcapture-assets
      - S3_ENDPOINT=http://minio:9000
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      - postgres
      - redis
      - minio
    networks:
      - trustcapture-network
    deploy:
      replicas: 3
      restart_policy:
        condition: on-failure

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=trustcapture
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - trustcapture-network

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    networks:
      - trustcapture-network

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    volumes:
      - minio-data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    networks:
      - trustcapture-network

  frontend:
    build: ./web
    environment:
      - VITE_API_BASE_URL=https://api.trustcapture.com
    depends_on:
      - backend
    networks:
      - trustcapture-network

volumes:
  postgres-data:
  redis-data:
  minio-data:

networks:
  trustcapture-network:
    driver: bridge
```

**Nginx Configuration for Custom Domains**:

```nginx
# nginx.conf
http {
    # Map custom domains to tenant IDs
    map $host $tenant_domain {
        default "";
        verify.agency-a.com "agency-a.com";
        verify.agency-b.com "agency-b.com";
    }

    upstream backend {
        server backend:8000;
    }

    server {
        listen 80;
        server_name _;

        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Custom-Domain $tenant_domain;
        }

        location / {
            proxy_pass http://frontend:3000;
            proxy_set_header Host $host;
        }
    }
}
```

### Dedicated Instance Deployment

**Terraform Configuration**:

```hcl
# terraform/main.tf

variable "tenant_name" {
  description = "Tenant name for dedicated instance"
  type        = string
}

variable "custom_domain" {
  description = "Custom domain for tenant"
  type        = string
}

module "vpc" {
  source = "./modules/vpc"
  tenant_name = var.tenant_name
}

module "database" {
  source = "./modules/database"
  tenant_name = var.tenant_name
  vpc_id = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
}

module "redis" {
  source = "./modules/redis"
  tenant_name = var.tenant_name
  vpc_id = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
}

module "s3" {
  source = "./modules/s3"
  tenant_name = var.tenant_name
}

module "ecs" {
  source = "./modules/ecs"
  tenant_name = var.tenant_name
  vpc_id = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
  database_url = module.database.connection_string
  redis_url = module.redis.connection_string
  s3_bucket = module.s3.bucket_name
}

module "alb" {
  source = "./modules/alb"
  tenant_name = var.tenant_name
  vpc_id = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnet_ids
  target_group_arn = module.ecs.target_group_arn
  custom_domain = var.custom_domain
}

output "load_balancer_dns" {
  value = module.alb.dns_name
}

output "database_endpoint" {
  value = module.database.endpoint
}
```

**Terraform Module: ECS Backend**:

```hcl
# terraform/modules/ecs/main.tf

resource "aws_ecs_cluster" "main" {
  name = "trustcapture-${var.tenant_name}"
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "trustcapture-backend-${var.tenant_name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"

  container_definitions = jsonencode([
    {
      name  = "backend"
      image = "trustcapture/backend:latest"
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      environment = [
        {
          name  = "DATABASE_URL"
          value = var.database_url
        },
        {
          name  = "REDIS_URL"
          value = var.redis_url
        },
        {
          name  = "S3_BUCKET"
          value = var.s3_bucket
        },
        {
          name  = "TENANT_ID"
          value = var.tenant_name
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/trustcapture-${var.tenant_name}"
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "backend"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "backend" {
  name            = "trustcapture-backend-${var.tenant_name}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.backend.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }
}
```

### Database Migration Strategy

**Initial Migration**: Add tenant_config table and tenant_id columns

```sql
-- Migration: 001_add_multi_tenancy.sql

-- Create tenant_config table
CREATE TABLE tenant_config (
    tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    primary_color VARCHAR(7) NOT NULL DEFAULT '#1E40AF',
    secondary_color VARCHAR(7) NOT NULL DEFAULT '#3B82F6',
    accent_color VARCHAR(7) NOT NULL DEFAULT '#60A5FA',
    logo_url TEXT,
    brand_name VARCHAR(255) NOT NULL,
    custom_domain VARCHAR(255) UNIQUE,
    contact_email VARCHAR(255) NOT NULL,
    support_phone VARCHAR(20),
    company_legal_name VARCHAR(255) NOT NULL,
    feature_flags JSONB NOT NULL DEFAULT '{}',
    rate_limit_requests_per_minute INTEGER DEFAULT 60,
    rate_limit_verifications_per_day INTEGER DEFAULT 1000,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT valid_primary_color CHECK (primary_color ~ '^#[0-9A-Fa-f]{6}$'),
    CONSTRAINT valid_secondary_color CHECK (secondary_color ~ '^#[0-9A-Fa-f]{6}$'),
    CONSTRAINT valid_accent_color CHECK (accent_color ~ '^#[0-9A-Fa-f]{6}$'),
    CONSTRAINT valid_email CHECK (contact_email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

-- Create default tenant for existing data
INSERT INTO tenant_config (
    brand_name, 
    company_legal_name, 
    contact_email
) VALUES (
    'TrustCapture', 
    'TrustCapture Inc.', 
    'support@trustcapture.com'
) RETURNING tenant_id;

-- Add tenant_id to existing tables (nullable initially)
ALTER TABLE clients ADD COLUMN tenant_id UUID REFERENCES tenant_config(tenant_id);
ALTER TABLE vendors ADD COLUMN tenant_id UUID REFERENCES tenant_config(tenant_id);
ALTER TABLE campaigns ADD COLUMN tenant_id UUID REFERENCES tenant_config(tenant_id);
ALTER TABLE photos ADD COLUMN tenant_id UUID REFERENCES tenant_config(tenant_id);
ALTER TABLE audit_logs ADD COLUMN tenant_id UUID REFERENCES tenant_config(tenant_id);

-- Update existing data to use default tenant
UPDATE clients SET tenant_id = (SELECT tenant_id FROM tenant_config WHERE brand_name = 'TrustCapture');
UPDATE vendors SET tenant_id = (SELECT tenant_id FROM tenant_config WHERE brand_name = 'TrustCapture');
UPDATE campaigns SET tenant_id = (SELECT tenant_id FROM tenant_config WHERE brand_name = 'TrustCapture');
UPDATE photos SET tenant_id = (SELECT tenant_id FROM tenant_config WHERE brand_name = 'TrustCapture');
UPDATE audit_logs SET tenant_id = (SELECT tenant_id FROM tenant_config WHERE brand_name = 'TrustCapture');

-- Make tenant_id NOT NULL after backfill
ALTER TABLE clients ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE vendors ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE campaigns ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE photos ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE audit_logs ALTER COLUMN tenant_id SET NOT NULL;

-- Create indexes for performance
CREATE INDEX idx_tenant_config_custom_domain ON tenant_config(custom_domain);
CREATE INDEX idx_tenant_config_brand_name ON tenant_config(brand_name);
CREATE INDEX idx_clients_tenant_id ON clients(tenant_id);
CREATE INDEX idx_vendors_tenant_id ON vendors(tenant_id);
CREATE INDEX idx_campaigns_tenant_id ON campaigns(tenant_id);
CREATE INDEX idx_photos_tenant_id ON photos(tenant_id);
CREATE INDEX idx_audit_logs_tenant_id ON audit_logs(tenant_id);

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenant_config_updated_at
    BEFORE UPDATE ON tenant_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### Monitoring and Observability

**Metrics to Collect**:
- Per-tenant API request count and latency
- Per-tenant verification count
- Per-tenant storage usage
- Per-tenant rate limit hits
- Cache hit/miss ratio for branding configuration
- Database query performance by tenant
- Error rates by tenant

**Prometheus Metrics Example**:

```python
# backend/app/core/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# Request metrics
tenant_requests_total = Counter(
    'tenant_requests_total',
    'Total requests per tenant',
    ['tenant_id', 'method', 'endpoint', 'status']
)

tenant_request_duration = Histogram(
    'tenant_request_duration_seconds',
    'Request duration per tenant',
    ['tenant_id', 'method', 'endpoint']
)

# Branding cache metrics
branding_cache_hits = Counter(
    'branding_cache_hits_total',
    'Branding cache hits',
    ['tenant_id']
)

branding_cache_misses = Counter(
    'branding_cache_misses_total',
    'Branding cache misses',
    ['tenant_id']
)

# Rate limit metrics
rate_limit_exceeded = Counter(
    'rate_limit_exceeded_total',
    'Rate limit exceeded count',
    ['tenant_id', 'limit_type']
)

# Storage metrics
tenant_storage_bytes = Gauge(
    'tenant_storage_bytes',
    'Storage used by tenant',
    ['tenant_id']
)

# Verification metrics
tenant_verifications_total = Counter(
    'tenant_verifications_total',
    'Total verifications per tenant',
    ['tenant_id', 'status']
)
```

**Grafana Dashboard Configuration**:

```json
{
  "dashboard": {
    "title": "Multi-Tenant Monitoring",
    "panels": [
      {
        "title": "Requests per Tenant",
        "targets": [
          {
            "expr": "sum(rate(tenant_requests_total[5m])) by (tenant_id)"
          }
        ]
      },
      {
        "title": "Request Latency by Tenant",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(tenant_request_duration_seconds_bucket[5m])) by (tenant_id, le))"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "targets": [
          {
            "expr": "sum(rate(branding_cache_hits_total[5m])) / (sum(rate(branding_cache_hits_total[5m])) + sum(rate(branding_cache_misses_total[5m])))"
          }
        ]
      },
      {
        "title": "Rate Limit Violations",
        "targets": [
          {
            "expr": "sum(rate(rate_limit_exceeded_total[5m])) by (tenant_id)"
          }
        ]
      },
      {
        "title": "Storage Usage by Tenant",
        "targets": [
          {
            "expr": "tenant_storage_bytes"
          }
        ]
      }
    ]
  }
}
```

### Security Considerations

**Tenant Isolation**:
- All database queries MUST include tenant_id filter
- Use SQLAlchemy query filters to automatically add tenant_id
- Implement row-level security (RLS) in PostgreSQL as defense-in-depth
- Regular automated testing of tenant isolation

**Authentication and Authorization**:
- JWT tokens MUST include tenant_id claim
- Validate tenant_id in JWT matches requested resources
- Admin endpoints require separate admin role claim
- API keys are scoped to specific tenant

**Data Encryption**:
- Encrypt sensitive data at rest (database encryption)
- Use TLS for all API communication
- Encrypt S3 objects with server-side encryption
- Rotate encryption keys regularly

**Audit Logging**:
- Log all tenant identification events
- Log all cross-tenant access attempts (should be denied)
- Log all branding configuration changes
- Log all admin actions
- Retain audit logs for compliance (90 days minimum)

**Rate Limiting**:
- Implement rate limiting per tenant to prevent abuse
- Use Redis for distributed rate limiting
- Return 429 with Retry-After header
- Monitor rate limit violations per tenant

### Performance Optimization

**Caching Strategy**:
- Cache branding configuration in Redis (1-hour TTL)
- Cache feature flags in Redis (5-minute TTL)
- Cache custom domain mappings in Redis (1-hour TTL)
- Invalidate cache on configuration updates

**Database Optimization**:
- Index all tenant_id foreign keys
- Use connection pooling (SQLAlchemy pool)
- Implement query result caching for expensive queries
- Regular VACUUM and ANALYZE on PostgreSQL

**CDN Configuration**:
- Serve tenant logos from CDN
- Cache static assets with tenant-specific paths
- Use CloudFront or similar CDN
- Set appropriate cache headers (1 day for logos)

**API Optimization**:
- Implement response compression (gzip)
- Use async/await for I/O operations
- Batch database queries where possible
- Implement pagination for list endpoints

## Implementation Guidance

### Phase 1: Backend Multi-Tenancy (Weeks 1-3)

**Week 1: Database and Models**
1. Create database migration for tenant_config table
2. Add tenant_id columns to existing tables
3. Create TenantConfig SQLAlchemy model
4. Create Pydantic schemas for tenant configuration
5. Run migration and verify schema

**Week 2: Middleware and Services**
1. Implement TenantMiddleware for tenant identification
2. Implement BrandingService with caching
3. Implement TenantService for tenant management
4. Add tenant context to request state
5. Update existing services to use tenant context

**Week 3: API Endpoints and Testing**
1. Implement branding API endpoints
2. Implement tenant management API endpoints
3. Add tenant_id filtering to all existing endpoints
4. Write unit tests for new components
5. Write property-based tests for tenant isolation

### Phase 2: Frontend Theming (Weeks 4-5)

**Week 4: Theme Context and Components**
1. Create ThemeContext and ThemeProvider
2. Implement branding API client
3. Create themed components (Logo, Button, Navigation)
4. Apply CSS custom properties
5. Update Tailwind configuration for dynamic colors

**Week 5: Integration and Testing**
1. Integrate theme context throughout application
2. Test with multiple tenant configurations
3. Implement loading and error states
4. Write unit tests for theme components
5. Write property-based tests for branding application

### Phase 3: Android White-Label (Weeks 6-8)

**Week 6: Build Variants**
1. Configure Gradle product flavors
2. Create flavor-specific resources (icons, strings, colors)
3. Set up flavor-specific package names
4. Test building multiple flavors

**Week 7: Dynamic Theming**
1. Implement ThemeManager for API-based theming
2. Implement branding API client
3. Apply branding to Material Theme
4. Implement caching for branding configuration

**Week 8: Testing and Distribution**
1. Test each flavor build
2. Test API-based theming
3. Test flavor precedence logic
4. Document build and distribution process
5. Create CI/CD pipeline for Android builds

### Phase 4: Deployment and Operations (Weeks 9-10)

**Week 9: Deployment Automation**
1. Create Docker Compose configuration
2. Create Terraform modules for dedicated instances
3. Set up CI/CD pipeline for deployments
4. Test multi-tenant deployment
5. Test dedicated instance deployment

**Week 10: Monitoring and Documentation**
1. Implement Prometheus metrics
2. Create Grafana dashboards
3. Set up alerting rules
4. Write deployment documentation
5. Write tenant onboarding documentation

### Development Best Practices

**Code Organization**:
- Keep tenant-related code in dedicated modules
- Use dependency injection for services
- Implement interfaces for testability
- Follow existing project structure

**Testing**:
- Write tests before implementation (TDD)
- Achieve >80% code coverage
- Run property-based tests in CI/CD
- Test tenant isolation for every endpoint

**Documentation**:
- Document all API endpoints with OpenAPI
- Document configuration options
- Document deployment procedures
- Document troubleshooting guides

**Security**:
- Review all code for tenant isolation
- Never trust client-provided tenant_id
- Always validate tenant_id from JWT
- Log all security-relevant events

**Performance**:
- Profile database queries
- Monitor cache hit rates
- Optimize slow endpoints
- Load test with multiple tenants

### Rollout Strategy

**Phase 1: Internal Testing**
- Deploy to staging environment
- Create test tenants
- Test all functionality
- Fix bugs and issues

**Phase 2: Beta Testing**
- Select 2-3 pilot customers
- Create their tenant configurations
- Monitor closely for issues
- Gather feedback

**Phase 3: General Availability**
- Announce feature to all customers
- Provide migration guide
- Offer onboarding assistance
- Monitor system performance

**Rollback Plan**:
- Keep feature flag to disable multi-tenancy
- Maintain backward compatibility
- Have database rollback scripts ready
- Monitor error rates closely

