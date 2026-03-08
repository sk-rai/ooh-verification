# TrustCapture - Requirements Traceability Matrix

**Last Updated**: 2026-03-04 (Task 3 Complete)  
**Project**: TrustCapture - Tamper-Proof Photo Verification System  
**Purpose**: Track requirements → design → tasks → implementation

---

## Legend

**Status Values**:
- ✅ **Complete** - Fully implemented and tested
- 🚧 **In Progress** - Currently being worked on
- ⏳ **Planned** - Scheduled but not started
- ⏸️ **Blocked** - Waiting on dependencies
- ❌ **Not Started** - Not yet begun

**Priority**:
- 🔴 **Critical** - Core functionality, must have
- 🟡 **High** - Important for MVP
- 🟢 **Medium** - Nice to have
- ⚪ **Low** - Future enhancement

---

## Phase 1: Backend Foundation

### Task 1: Project Setup
**Status**: ✅ Complete  
**Completed**: 2026-03-04  
**Priority**: 🔴 Critical

| Requirement | Design Section | Implementation | Status | Notes |
|-------------|----------------|----------------|--------|-------|
| Req 20 (Min SDK) | Tech Stack | `requirements.txt`, `.env.example` | ✅ | Python 3.11+, FastAPI 0.109.0 |
| Req 20 (Compatibility) | Infrastructure | Docker setup, Alembic config | ✅ | PostgreSQL 15+ support |

**Deliverables**:
- ✅ FastAPI project structure
- ✅ requirements.txt with all dependencies
- ✅ .env.example configuration template
- ✅ Docker and docker-compose files
- ✅ pytest configuration

---


### Task 2: Database Schema and Models
**Status**: ✅ Complete  
**Started**: 2026-03-04  
**Completed**: 2026-03-04  
**Priority**: 🔴 Critical

#### Task 2.1: Create PostgreSQL Database Schema

| Requirement | Design Section | Implementation | Status | File | Notes |
|-------------|----------------|----------------|--------|------|-------|
| Req 1.1 (Client Registration) | Client Management | `clients` table | ✅ | `models/client.py` | Email, password, subscription |
| Req 1.2 (Subscription Tiers) | Subscription Model | `subscriptions` table | ✅ | `models/subscription.py` | Free/Pro/Enterprise |
| Req 1.1 (Vendor Creation) | Vendor Management | `vendors` table | ✅ | `models/vendor.py` | 6-char alphanumeric ID |
| Req 1.3 (SMS Delivery) | Vendor Management | `vendors.phone_number` | ✅ | `models/vendor.py` | Phone number field |
| Req 12.6 (Public Key Storage) | Crypto Security | `vendors.public_key` | ✅ | `models/vendor.py` | RSA/ECDSA public key |
| Req 1.1 (Campaign Creation) | Campaign Management | `campaigns` table | ✅ | `models/campaign.py` | Campaign codes |
| Req 1.4 (Campaign Expiration) | Campaign Management | `campaigns.start_date/end_date` | ✅ | `models/campaign.py` | Date range validation |
| Req 18.1-18.5 (Multi-Domain) | Campaign Types | `campaigns.campaign_type` enum | ✅ | `models/campaign.py` | 6 industry types |
| Req 3.1 (GPS Precision) | Sensor Data | `sensor_data.gps_latitude/longitude` | ✅ | `models/sensor_data.py` | DECIMAL(10,7) = 7 decimals |
| Req 3.2 (GPS Metadata) | Sensor Data | `sensor_data.gps_*` columns | ✅ | `models/sensor_data.py` | Accuracy, altitude, provider |
| Req 4.1-4.8 (WiFi Scanning) | Sensor Data | `sensor_data.wifi_networks` JSONB | ✅ | `models/sensor_data.py` | SSID, BSSID, signal |
| Req 5.1-5.7 (Cell Towers) | Sensor Data | `sensor_data.cell_towers` JSONB | ✅ | `models/sensor_data.py` | Cell ID, LAC, MCC, MNC |
| Req 6.1-6.6 (Triangulation) | Location Triangulator | `sensor_data` table | ✅ | `models/sensor_data.py` | Combined sensor data |
| Req 6.5 (Location Hash) | Location Hash | `sensor_data.location_hash` | ✅ | `models/sensor_data.py` | SHA-256 hash |
| Req 7.1-7.8 (Profile Matching) | Location Profile | `location_profiles` table | ✅ | `models/location_profile.py` | Expected sensor patterns |
| Req 8.1-8.7 (Crypto Signing) | Photo Signature | `photo_signatures` table | ✅ | `models/photo_signature.py` | RSA/ECDSA signatures |
| Req 9.1 (Photo Upload) | Photo Storage | `photos` table | ✅ | `models/photo.py` | S3 keys, metadata |
| Req 9.3 (S3 Storage) | Photo Storage | `photos.s3_key/thumbnail_s3_key` | ✅ | `models/photo.py` | S3 object paths |
| Req 27.1-27.6 (Signature Verify) | Verification Service | `photos.signature_valid` | ✅ | `models/photo.py` | Boolean verification |
| Req 30.1-30.6 (GPS Accuracy) | GPS Sensor | `sensor_data.gps_accuracy` | ✅ | `models/sensor_data.py` | Accuracy in meters |
| Property 7 (GPS Precision) | Sensor Data | DECIMAL(10,7) type | ✅ | `models/sensor_data.py` | 7 decimal places |
| Property 12 (Campaign Code) | Campaign Validator | `campaigns.campaign_code` unique | ✅ | `models/campaign.py` | Alphanumeric with hyphens |

**Deliverables**:
- ✅ 9 SQLAlchemy models created
- ✅ 20 database indexes defined
- ✅ 6 enum types for type safety
- ✅ 8 foreign key relationships
- ✅ 10 unique constraints

**Files Created**:
- ✅ `backend/app/models/client.py`
- ✅ `backend/app/models/vendor.py`
- ✅ `backend/app/models/campaign.py`
- ✅ `backend/app/models/location_profile.py`
- ✅ `backend/app/models/campaign_vendor_assignment.py`
- ✅ `backend/app/models/photo.py`
- ✅ `backend/app/models/sensor_data.py`
- ✅ `backend/app/models/photo_signature.py`
- ✅ `backend/app/models/subscription.py`
- ✅ `backend/app/models/__init__.py`

---

#### Task 2.2: Create SQLAlchemy ORM Models

| Requirement | Design Section | Implementation | Status | Notes |
|-------------|----------------|----------------|--------|-------|
| All models | ORM Layer | SQLAlchemy 2.0 async models | ✅ | Full async/await support |
| Relationships | Data Models | back_populates, cascade rules | ✅ | Proper foreign key handling |
| Validation | Pydantic Integration | Enum types, constraints | ✅ | Type-safe enums |

**Deliverables**:
- ✅ All models with proper relationships
- ✅ Cascade delete rules configured
- ✅ Enum types for status fields
- ✅ Model __repr__ methods for debugging

---

#### Task 2.3: Write Property Tests
**Status**: ⏳ Planned  
**Priority**: 🟡 High

| Property | Requirement | Implementation | Status | Notes |
|----------|-------------|----------------|--------|-------|
| Property 1 (Config Round-Trip) | Req 25.4 | Configuration parser test | ⏳ | parse(print(C)) == C |
| Property 2 (Sensor Round-Trip) | Req 26.6 | Sensor data serialization test | ⏳ | deserialize(serialize(S)) == S |
| Property 7 (GPS Precision) | Req 3.1, 30.1 | GPS coordinate test | ⏳ | 7 decimal preservation |

**Planned Deliverables**:
- ⏳ Kotest property-based tests
- ⏳ Hypothesis tests for Python
- ⏳ Test coverage report

---

#### Task 2.4: Create Initial Database Migration

| Requirement | Design Section | Implementation | Status | File | Notes |
|-------------|----------------|----------------|--------|------|-------|
| All tables | Database Schema | Alembic migration | ✅ | `alembic/versions/20260304_initial_schema.py` | All 9 tables |
| Indexes | Performance | CREATE INDEX statements | ✅ | Migration file | 20 indexes |
| Enums | Type Safety | CREATE TYPE statements | ✅ | Migration file | 6 enum types |
| Foreign Keys | Data Integrity | FOREIGN KEY constraints | ✅ | Migration file | CASCADE DELETE |

**Deliverables**:
- ✅ Initial migration file created
- ✅ Alembic configuration (`alembic.ini`)
- ✅ Async migration environment (`alembic/env.py`)
- ✅ Migration template (`alembic/script.py.mako`)
- ✅ Database documentation (`DATABASE.md`)
- ✅ Quick start guide (`QUICKSTART.md`)
- ✅ Implementation summary (`DB_IMPLEMENTATION_SUMMARY.md`)
- ✅ Database setup script (`scripts/db_setup.py`)

**Files Created**:
- ✅ `backend/alembic.ini`
- ✅ `backend/alembic/env.py`
- ✅ `backend/alembic/script.py.mako`
- ✅ `backend/alembic/versions/20260304_initial_schema.py`
- ✅ `backend/app/core/database.py`
- ✅ `backend/scripts/db_setup.py`
- ✅ `backend/DATABASE.md`
- ✅ `backend/QUICKSTART.md`
- ✅ `backend/DB_IMPLEMENTATION_SUMMARY.md`
- ✅ `backend/README.md`

---

### Task 3: Authentication and Authorization
**Status**: ⏳ Planned  
**Priority**: 🔴 Critical

#### Task 3.1: JWT Authentication for Web Clients

| Requirement | Design Section | Implementation | Status | Notes |
|-------------|----------------|----------------|--------|-------|
| Req 1.1 (Client Login) | Authentication | JWT token generation | ⏳ | python-jose |
| Req 1.2 (Token Validation) | Authentication | JWT middleware | ⏳ | FastAPI Depends |
| Password Hashing | Security | bcrypt hashing | ⏳ | passlib |

**Planned Deliverables**:
- ⏳ JWT token generation service
- ⏳ Token validation middleware
- ⏳ Password hashing utilities
- ⏳ Refresh token mechanism

---

#### Task 3.2: Vendor Authentication System

| Requirement | Design Section | Implementation | Status | Notes |
|-------------|----------------|----------------|--------|-------|
| Req 1.4 (Vendor Login) | Vendor Auth | Phone + Vendor ID auth | ⏳ | OTP verification |
| OTP Generation | SMS Integration | Twilio integration | ⏳ | 6-digit OTP |
| Device Registration | Security | Device ID + public key | ⏳ | Android Keystore |

**Planned Deliverables**:
- ⏳ OTP generation and validation
- ⏳ Twilio SMS integration
- ⏳ Device registration endpoint
- ⏳ Public key storage

---

#### Task 3.3: Unit Tests for Authentication

| Test Type | Coverage | Status | Notes |
|-----------|----------|--------|-------|
| Password Hashing | bcrypt operations | ⏳ | Hash and verify |
| JWT Generation | Token creation | ⏳ | Valid tokens |
| JWT Validation | Token verification | ⏳ | Expired, invalid tokens |
| OTP Generation | 6-digit codes | ⏳ | Expiration handling |

---

### Task 4: Client Management API
**Status**: ⏳ Planned  
**Priority**: 🔴 Critical

| Requirement | Endpoint | Status | Notes |
|-------------|----------|--------|-------|
| Req 1.1 (Registration) | POST /api/clients/register | ⏳ | Email validation |
| Req 1.2 (Login) | POST /api/clients/login | ⏳ | JWT token return |
| Email Validation | Registration | ⏳ | SendGrid integration |

---

### Task 5: Checkpoint
**Status**: ⏳ Planned  
**Purpose**: Ensure all tests pass before proceeding

---

### Task 6: Vendor Management API
**Status**: ⏳ Planned  
**Priority**: 🔴 Critical

| Requirement | Endpoint | Status | Notes |
|-------------|----------|--------|-------|
| Req 1.1 (Create Vendor) | POST /api/vendors | ⏳ | Generate 6-char ID |
| Req 1.2 (List Vendors) | GET /api/vendors | ⏳ | Filter by client |
| Req 1.3 (SMS Delivery) | Vendor creation | ⏳ | Twilio integration |
| Vendor Deactivation | PATCH /api/vendors/{id}/deactivate | ⏳ | Status update |

---

### Task 7: Campaign Management API
**Status**: ⏳ Planned  
**Priority**: 🔴 Critical

| Requirement | Endpoint | Status | Notes |
|-------------|----------|--------|-------|
| Req 1.1 (Create Campaign) | POST /api/campaigns | ⏳ | Generate campaign code |
| Req 7.1-7.4 (Location Profile) | Location profile creation | ⏳ | Expected sensor data |
| Vendor Assignment | POST /api/campaigns/{id}/vendors | ⏳ | Many-to-many link |

---


## Phase 2: Web Application (Client Portal)

### Tasks 18-33: Web Application Development
**Status**: ⏳ Planned  
**Priority**: 🟡 High

| Task | Component | Status | Dependencies |
|------|-----------|--------|--------------|
| Task 18 | Project Setup (React + TypeScript) | ⏳ | None |
| Task 19 | Authentication UI | ⏳ | Task 3 (Backend Auth) |
| Task 20 | Subscription Selection UI | ⏳ | Task 15 (Stripe) |
| Task 22 | Client Dashboard | ⏳ | Task 4 (Client API) |
| Task 23 | Vendor Management UI | ⏳ | Task 6 (Vendor API) |
| Task 25 | Campaign Management UI | ⏳ | Task 7 (Campaign API) |
| Task 26 | Photo Gallery UI | ⏳ | Task 12 (Photo API) |
| Task 28 | Map Visualization | ⏳ | Task 12 (Photo API) |
| Task 29 | Reports & Analytics UI | ⏳ | Task 16 (Reports API) |
| Task 31 | Settings & Account Management | ⏳ | Task 4, 15 |

---

## Phase 3: Android Application (Vendor App)

### Tasks 34-60: Android Application Development
**Status**: ⏳ Planned  
**Priority**: 🔴 Critical

| Task | Component | Status | Dependencies |
|------|-----------|--------|--------------|
| Task 34 | Android Project Setup | ⏳ | None |
| Task 35 | Permission Management | ⏳ | Task 34 |
| Task 36 | Android Keystore Integration | ⏳ | Task 34 |
| Task 38 | Sensor Data Collection | ⏳ | Task 35 |
| Task 39 | Location Triangulation | ⏳ | Task 38 |
| Task 41 | Photo Capture Module | ⏳ | Task 35 |
| Task 42 | Watermark Generation | ⏳ | Task 41 |
| Task 43 | Cryptographic Signing | ⏳ | Task 36 |
| Task 45 | Encryption & Local Storage | ⏳ | Task 36 |
| Task 46 | Upload Manager | ⏳ | Task 12 (Backend) |
| Task 48 | Campaign Validation | ⏳ | Task 7 (Backend) |
| Task 51 | UI Screens (Jetpack Compose) | ⏳ | All above |

---

## Requirements Coverage Summary

### Authentication & Authorization (Req 1.x)
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Req 1.1 (Client Registration) | ✅ | Task 2.1 | `clients` table |
| Req 1.1 (Vendor Creation) | ✅ | Task 2.1 | `vendors` table |
| Req 1.2 (Campaign Code) | ✅ | Task 2.1 | `campaigns.campaign_code` |
| Req 1.3 (SMS Delivery) | ✅ | Task 2.1 | `vendors.phone_number` |
| Req 1.4 (Campaign Expiration) | ✅ | Task 2.1 | `campaigns.start_date/end_date` |

### Photo Capture (Req 2.x)
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Req 2.1 (Rear Camera) | ⏳ | Task 41 | Android CameraX |
| Req 2.2 (Live Preview) | ⏳ | Task 41 | Camera preview |
| Req 2.3 (Gallery Block) | ⏳ | Task 41 | Permission enforcement |

### GPS Verification (Req 3.x)
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Req 3.1 (7 Decimal Precision) | ✅ | Task 2.1 | DECIMAL(10,7) |
| Req 3.2 (GPS Metadata) | ✅ | Task 2.1 | `sensor_data.gps_*` |
| Req 3.3 (Accuracy Warning) | ⏳ | Task 38 | Android GPS sensor |

### WiFi Fingerprinting (Req 4.x)
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Req 4.1 (WiFi Scanning) | ✅ | Task 2.1 | `sensor_data.wifi_networks` JSONB |
| Req 4.2 (SSID/BSSID) | ✅ | Task 2.1 | JSONB structure |
| Req 4.3 (5+ Networks) | ⏳ | Task 38 | Android WiFi scanner |

### Cell Tower (Req 5.x)
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Req 5.1 (Cell Tower Data) | ✅ | Task 2.1 | `sensor_data.cell_towers` JSONB |
| Req 5.2 (Cell ID/LAC/MCC/MNC) | ✅ | Task 2.1 | JSONB structure |

### Multi-Sensor Triangulation (Req 6.x)
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Req 6.1 (Combined Data) | ✅ | Task 2.1 | `sensor_data` table |
| Req 6.2 (Confidence Score) | ✅ | Task 2.1 | `sensor_data.confidence_score` |
| Req 6.5 (Location Hash) | ✅ | Task 2.1 | `sensor_data.location_hash` |

### Location Profile Matching (Req 7.x)
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Req 7.1 (Profile Comparison) | ✅ | Task 2.1 | `location_profiles` table |
| Req 7.2 (GPS Tolerance) | ✅ | Task 2.1 | `tolerance_meters` |
| Req 7.3 (WiFi Matching) | ✅ | Task 2.1 | `expected_wifi_bssids` |
| Req 7.4 (Cell Matching) | ✅ | Task 2.1 | `expected_cell_tower_ids` |
| Req 7.5 (Match Result) | ✅ | Task 2.1 | `photos.location_match_score` |

### Cryptographic Security (Req 8.x)
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Req 8.1 (Photo Signing) | ✅ | Task 2.1 | `photo_signatures` table |
| Req 8.2 (Hardware Keystore) | ⏳ | Task 36 | Android Keystore |
| Req 8.3 (Signature Metadata) | ✅ | Task 2.1 | `photo_signatures.*` |
| Req 12.6 (Public Key Storage) | ✅ | Task 2.1 | `vendors.public_key` |

### Upload & Storage (Req 9.x)
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Req 9.1 (Photo Upload) | ✅ | Task 2.1 | `photos` table |
| Req 9.2 (TLS 1.3) | ⏳ | Task 12 | FastAPI HTTPS |
| Req 9.3 (S3 Storage) | ✅ | Task 2.1 | `photos.s3_key` |

### Multi-Domain Campaigns (Req 18.x)
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Req 18.1 (Construction) | ✅ | Task 2.1 | `campaign_type` enum |
| Req 18.2 (Insurance) | ✅ | Task 2.1 | `campaign_type` enum |
| Req 18.3 (Delivery) | ✅ | Task 2.1 | `campaign_type` enum |
| Req 18.4 (Healthcare) | ✅ | Task 2.1 | `campaign_type` enum |
| Req 18.5 (Property Mgmt) | ✅ | Task 2.1 | `campaign_type` enum |

### Subscription Management
| Requirement | Status | Task | Implementation |
|-------------|--------|------|----------------|
| Free Tier (50 photos) | ✅ | Task 2.1 | `subscriptions.photos_quota` |
| Pro Tier (Unlimited) | ✅ | Task 2.1 | `subscriptions.tier` |
| Stripe Integration | ✅ | Task 2.1 | `subscriptions.stripe_subscription_id` |

---

## Property-Based Testing Coverage

| Property | Requirement | Status | Task | Notes |
|----------|-------------|--------|------|-------|
| Property 1 (Config Round-Trip) | Req 25.4 | ⏳ | Task 2.3 | parse(print(C)) == C |
| Property 2 (Sensor Round-Trip) | Req 26.6 | ⏳ | Task 2.3 | deserialize(serialize(S)) == S |
| Property 3 (Signature Verify) | Req 8.7, 27.6 | ⏳ | Task 9.2 | verify(sign(P)) == true |
| Property 4 (Hash Determinism) | Req 6.5, 28.1 | ⏳ | Task 9.5 | hash(S) == hash(S) |
| Property 5 (Hash Uniqueness) | Req 28.4, 28.5 | ⏳ | Task 9.6 | hash(S1) != hash(S2) |
| Property 7 (GPS Precision) | Req 3.1, 30.1 | ⏳ | Task 2.3 | 7 decimals preserved |
| Property 12 (Campaign Code) | Req 1.1, 12.1 | ⏳ | Task 7.4 | [A-Z0-9]+(-[A-Z0-9]+)* |

---

## Progress Summary

### Overall Progress
- **Phase 1 (Backend)**: 4/17 tasks complete (24%)
- **Phase 2 (Web App)**: 0/16 tasks complete (0%)
- **Phase 3 (Android)**: 0/27 tasks complete (0%)
- **Total**: 4/60 tasks complete (7%)

### Requirements Coverage
- **Database Requirements**: 100% (All Req 1.x, 3.x, 4.x, 5.x, 6.x, 7.x, 8.x, 9.x, 18.x)
- **Authentication Requirements**: 50% (Models done, APIs pending)
- **Photo Capture Requirements**: 10% (Models done, Android pending)
- **Overall Requirements**: ~25% complete

### By Priority
- **🔴 Critical**: 4/30 complete (13%)
- **🟡 High**: 0/20 complete (0%)
- **🟢 Medium**: 0/8 complete (0%)
- **⚪ Low**: 0/2 complete (0%)

---

## Next Milestone: Authentication (Task 3)

**Target Date**: TBD  
**Dependencies**: Task 2 (Complete ✅)

**Deliverables**:
1. JWT authentication for web clients
2. Vendor OTP authentication
3. Password hashing utilities
4. Authentication middleware
5. Unit tests for auth flows

**Requirements Covered**:
- Req 1.1 (Client Login)
- Req 1.2 (Token Validation)
- Req 1.4 (Vendor Login)
- Req 15.1-15.6 (Permission Management)

---

## Change Log

| Date | Task | Status Change | Notes |
|------|------|---------------|-------|
| 2026-03-04 | Task 1 | ⏳ → ✅ | Project setup complete |
| 2026-03-04 | Task 2.1 | ⏳ → ✅ | Database schema created |
| 2026-03-04 | Task 2.2 | ⏳ → ✅ | SQLAlchemy models created |
| 2026-03-04 | Task 4 | 🚧 → ✅ | Client Management API complete |
| 2026-03-04 | Task 4 | ⏳ → 🚧 | Client Management API started |
| 2026-03-04 | Task 3.1 | ⏳ → ✅ | JWT authentication complete |
| 2026-03-04 | Task 3.2 | ⏳ → ✅ | Vendor OTP authentication complete |
| 2026-03-04 | Task 2.4 | ⏳ → ✅ | Initial migration created |

---

## Notes

- This matrix is updated at the start and end of each task
- All requirements are traced to design sections and implementation files
- Property-based tests are tracked separately for quality assurance
- Dependencies between tasks are clearly marked
- Status changes are logged in the change log

**Last Review**: 2026-03-04  
**Next Review**: Before starting Task 3 (Authentication)

