# TrustCapture Platform Evolution Plan

## Status: PLANNING (Implementation target: 2-3 week sprint)

Last updated: July 2026

---

## Overview

This document consolidates all planned enhancements into a single implementation strategy. These features are driven by real customer conversations and will be implemented together in one development pass.

**Five workstreams converging:**
1. Campaign-free capture (event-driven evidence)
2. Multi-media support (video, voice notes, text notes)
3. Coordinate-only locations (pin drop, no address required)
4. 3rd party API integration (verification-as-a-service)
5. White-label foundation (runtime branding)

---

## Architecture Evolution: From "Photo Verification" to "Evidence Platform"

### Current Model
```
Campaign (planned) → Location (address) → Vendor (assigned) → Photo (single) → Verify against expected location
```

### New Model
```
Evidence Capture (planned OR spontaneous)
  → Campaign (optional)
  → Location (address OR coordinates OR route OR none)
  → Vendor (assigned OR self-directed)
  → Evidence (photo, video, voice, text — one or multiple)
  → Verify: device + liveness + location (if available) + continuity (for video)
```

---

## Workstream 1: Campaign-Free Capture

### Problem
Police accident scene, insurance damage reports, hazard reporting — no pre-planned campaign exists.

### Solution
- Make `campaign_id` nullable on evidence
- Add "Quick Capture" mode in Android (no campaign selection needed)
- Verification still runs: device attestation, liveness, GPS quality, freshness
- Location match is N/A (no expected location) — score based on available signals only

### New Concepts
- **Category/Tags**: "accident", "damage", "hazard", "inspection", "delivery_proof" (enum + freeform)
- **Cases/Incidents**: Group related captures after the fact (like folders)

### Backend Changes
- `photos` table (or new `evidence` table): `campaign_id` becomes nullable
- New fields: `category`, `case_id` (nullable FK to new `cases` table)
- New table: `cases` (case_id, tenant_id, client_id, title, description, status, created_at)
- Verification pipeline: skip location/pressure/magnetic checks when no campaign context
- Adjusted confidence scoring for campaign-free captures

---

## Workstream 2: Multi-Media Evidence

### Problem
Customers need video (continuous proof), voice notes (verbal observations), and written notes alongside photos.

### Solution
Unified evidence model supporting multiple media types per capture event.

### Evidence Types
| Type | File | Verification |
|------|------|-------------|
| Photo | JPEG, 1-5 MB | Full pipeline (current) |
| Video | MP4, 15-50 MB, max 60s | First-frame watermark + GPS track + file hash signature |
| Voice Note | M4A/AAC, 0.5-2 MB, max 120s | GPS at start/end + device signature |
| Text Note | None (stored in DB) | No verification (informational) |

### Video Verification Strategy
1. Record video normally (no per-frame watermark)
2. Capture GPS every 1 second during recording → store as GPS track
3. Watermark first frame only (timestamp + GPS + vendor ID)
4. At end: SHA-256 hash of video file + sign with device key
5. Verify: track continuity, duration match, all points within tolerance, signature valid

### Storage Strategy
| Media | Current Storage | Recommended |
|-------|----------------|-------------|
| Photo | Cloudinary (free 25GB) | Keep for now |
| Video | N/A | S3 ($0.023/GB) — Cloudinary free tier fills fast |
| Voice | N/A | S3 (or Cloudinary) |
| Text | N/A | PostgreSQL directly |

**Decision needed:** Cloudinary upgrade vs S3. S3 is cheaper long-term and gives more control.

### Database Schema

**Option A (Recommended): New `evidence` table replacing/alongside `photos`**

```sql
CREATE TABLE evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    campaign_id UUID REFERENCES campaigns(campaign_id),  -- NULLABLE for campaign-free
    vendor_id VARCHAR(6) NOT NULL REFERENCES vendors(vendor_id),
    case_id UUID REFERENCES cases(case_id),              -- NULLABLE, for grouping
    
    -- Type & Content
    evidence_type VARCHAR(20) NOT NULL,  -- 'photo', 'video', 'voice_note', 'text_note'
    category VARCHAR(50),                -- 'accident', 'inspection', 'delivery_proof', etc.
    
    -- File Storage
    file_key VARCHAR(500),               -- S3/Cloudinary key
    file_url VARCHAR(500),
    thumbnail_key VARCHAR(500),
    thumbnail_url VARCHAR(500),
    file_size_bytes BIGINT,
    mime_type VARCHAR(50),
    duration_seconds FLOAT,              -- For video/voice
    text_content TEXT,                   -- For text notes
    
    -- Capture Context
    capture_timestamp TIMESTAMPTZ,
    latitude FLOAT,
    longitude FLOAT,
    accuracy FLOAT,
    
    -- Verification
    verification_status VARCHAR(20) DEFAULT 'pending',
    verification_confidence FLOAT,
    verification_flags JSONB DEFAULT '[]',
    device_signature TEXT,
    
    -- Metadata
    notes TEXT,                           -- User-added notes alongside any media type
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',         -- Flexible: sensor snapshots, device info, etc.
    
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE gps_tracks (
    track_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id UUID NOT NULL REFERENCES evidence(evidence_id),
    points JSONB NOT NULL,               -- [{lat, lon, accuracy, timestamp}, ...]
    duration_seconds FLOAT,
    total_distance_meters FLOAT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE cases (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL REFERENCES clients(client_id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    status VARCHAR(20) DEFAULT 'open',   -- open, closed, archived
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**Migration strategy:** Keep existing `photos` + `sensor_data` tables working. New captures go to `evidence` table. Existing data migrated gradually or accessed via a unified view.

---

## Workstream 3: Coordinate-Only Locations

### Problem
Pipelines, transmission towers, remote areas, offshore — no street address exists.

### Solution
Locations already support lat/lon without address in the schema. Gaps are in the UI and bulk upload.

### Changes Needed
| Component | Change |
|-----------|--------|
| Frontend: campaign creation | Add "Drop Pin" map picker as alternative to address input |
| Frontend: location list | Show pin on map even without address |
| Backend: LocationProfile | Add `asset_id` (VARCHAR 100), `asset_type` (VARCHAR 50), `location_description` (TEXT) |
| Bulk upload | Ensure lat/lon-only rows work (already supported in `/api/bulk/campaign-setup`) |
| Future: Route/polyline | New `campaign_routes` table for linear infrastructure (pipeline paths) |

### Asset ID Examples
| Industry | asset_id | asset_type |
|----------|----------|-----------|
| Pipeline | KM-342 | pipeline_marker |
| Telecom | TWR-0047 | transmission_tower |
| Solar | ROW-12-COL-8 | solar_panel |
| Construction | ZONE-B-FLOOR-3 | construction_zone |

### Route/Polyline Verification (Future)
For pipelines: define a route as ordered lat/lon points. Verification checks if vendor GPS falls within X meters of any segment of the route. Effort: 3-4 days backend, 3-4 days frontend (route drawing UI).

---

## Workstream 4: 3rd Party API Integration

### Problem
External apps want to use TrustCapture as a verification layer without adopting the full platform.

### Solution
Stateless verification API + API key authentication.

### New Components
| Component | Purpose |
|-----------|---------|
| `api_keys` table | Server-to-server auth (no OTP/JWT needed) |
| `POST /api/v1/verify` | Stateless: send photo + GPS → get confidence score back |
| Webhook registration | `POST /api/v1/webhooks` — notify their backend on verification complete |
| Rate limiting | Per API key, configurable |
| Usage tracking | Count API calls per key per day for billing |

### API Key Model
```sql
CREATE TABLE api_keys (
    key_id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients(client_id),
    tenant_id UUID NOT NULL,
    key_hash VARCHAR(255) NOT NULL,       -- SHA-256 of actual key
    key_prefix VARCHAR(12) NOT NULL,      -- "tc_live_abc1" for identification
    name VARCHAR(100),
    permissions JSONB DEFAULT '["verify"]',
    rate_limit_per_minute INT DEFAULT 60,
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Verify Endpoint
```
POST /api/v1/verify
Headers: Authorization: Bearer tc_live_xxxxxxxx
Body: multipart (photo file + JSON metadata)

Response: {
  verification_id, confidence, status, flags, checks: {...}
}
```

---

## Workstream 5: White-Label Foundation

### Already Built (Backend)
- Multi-tenant isolation (tenant_id on all models)
- Tenant config: primary_color, secondary_color, logo_url, custom_domain
- Email templates with tenant branding
- Subdomain + custom domain resolution

### To Build (Phase 1 — Minimal)
| Component | What | Effort |
|-----------|------|--------|
| `GET /api/tenants/branding` | Public endpoint returning colors + logo for current tenant | 0.5 day |
| Web: CSS variables from tenant config | Fetch on login, inject into Tailwind | 2-3 days |
| Web: tenant logo in Navigation | Replace hardcoded "TrustCapture" | 0.5 day |
| Android: runtime branding | Fetch `/api/tenants/branding` on start → apply colors | 5-7 days |
| Android: watermark customization | Use tenant_name instead of "TrustCapture" | 1 day |

---

## Combined Implementation Plan (2-3 Week Sprint)

### Week 1: Foundation

| Day | Backend | Android |
|-----|---------|---------|
| 1-2 | New `evidence` table + `cases` table + migration. Keep `photos` table working alongside. | Plan evidence capture flow |
| 3 | `POST /api/evidence/upload` endpoint (accepts photo/video/voice/text, campaign optional) | Start video recording with GPS track |
| 4 | `gps_tracks` table + GPS track storage | Voice note recording |
| 5 | Video verification pipeline (track continuity + signature check) | Text note UI |

### Week 2: Features

| Day | Backend | Android |
|-----|---------|---------|
| 1 | `api_keys` table + API key auth middleware | "Quick Capture" mode (no campaign) |
| 2 | `POST /api/v1/verify` stateless endpoint | Category/tag selection UI |
| 3 | Webhook registration + delivery | Pin-drop location on map (campaign creation) |
| 4 | `asset_id` + `location_description` on LocationProfile. Bulk lat/lon upload. | Upload flow for video + voice |
| 5 | `GET /api/tenants/branding` + rate limiting | Runtime branding from API |

### Week 3: Polish & Integration

| Day | Backend | Android |
|-----|---------|---------|
| 1-2 | Reports: include video/voice in table data + dashboard. Quota updates. | Testing all flows |
| 3 | Frontend: evidence list (mixed types), video player, audio player | Watermark customization |
| 4 | Frontend: pin-drop map, asset ID field, case grouping | Build flavors setup |
| 5 | Integration testing, documentation, deploy | Final testing |

---

## Decisions Needed Before Starting

| # | Decision | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | Storage for video/voice | Cloudinary upgrade ($) vs S3 | S3 — cheaper, more control |
| 2 | Max video duration | 15s / 30s / 60s | 30s default, configurable per campaign |
| 3 | Max voice note duration | 60s / 120s / 300s | 120s |
| 4 | Evidence table: new vs extend photos | New table vs add columns to photos | New table (cleaner) |
| 5 | Campaign-free: category list | Fixed enum vs freeform | Enum with "other" + freeform |
| 6 | Chunked upload protocol | tus.io vs multipart | Multipart (simpler, works for 50MB) |
| 7 | API key format | `tc_live_xxx` / `tc_test_xxx` | Yes, with test/live distinction |

---

## Impact on Android (Context for Android Kiro)

### New Capabilities Required

1. **Video Recording**
   - CameraX VideoCapture use case (alongside existing ImageCapture)
   - Record GPS every 1 second during recording → store as track
   - Watermark first frame with timestamp + GPS + vendor ID
   - At end: compute SHA-256 of video file → sign with device key
   - Max duration: 30-60 seconds (configurable)

2. **Voice Note Recording**
   - MediaRecorder with AAC codec
   - Capture GPS at start and end
   - Sign file with device key at end
   - Max duration: 120 seconds

3. **Text Notes**
   - Simple text input field
   - Can be standalone or attached to photo/video
   - No device signature needed (informational only)

4. **Quick Capture Mode (No Campaign)**
   - New flow: open app → capture button → take photo/video/voice → select category → upload
   - No campaign selection required
   - Category picker: accident, damage, inspection, delivery_proof, hazard, other

5. **GPS Track During Video**
   - FusedLocationProviderClient with 1-second interval during video recording
   - Store as array: [{lat, lon, accuracy, timestamp}, ...]
   - Include in upload payload

6. **Pin-Drop Location (Campaign Creation via API)**
   - Not in mobile app (campaigns created via web dashboard)
   - But mobile needs to handle campaigns with coordinate-only locations (no address shown)
   - Display lat/lon or asset_id instead of address in campaign list

7. **Runtime Branding**
   - On app start: `GET /api/tenants/branding` (no auth)
   - Cache in DataStore: primary_color, secondary_color, logo_url, tenant_name
   - Apply to Material Theme dynamically
   - Use tenant_name in WatermarkGenerator

8. **Upload Changes**
   - New endpoint: `POST /api/evidence/upload`
   - Multipart: file + JSON metadata
   - Metadata includes: evidence_type, campaign_id (optional), category, notes, gps_track (for video)
   - Larger upload limit: 50MB (for video)
   - Handle upload progress indicator for large files

### Android Effort Estimate
| Feature | Effort |
|---------|--------|
| Video recording + GPS track + signing | 5-7 days |
| Voice note recording + signing | 2-3 days |
| Text note UI | 1 day |
| Quick Capture mode (no campaign flow) | 2-3 days |
| Category picker | 1 day |
| Upload refactor (evidence endpoint, larger files, progress) | 2-3 days |
| Runtime branding | 3-5 days |
| **Total Android** | **~2.5-3 weeks** |

---

## Migration Strategy

### Phase 1: Backend deploys new tables + endpoints
- `evidence` table created alongside existing `photos` table
- New `/api/evidence/upload` endpoint goes live
- Old `/api/photos/upload` continues to work (backward compatible)
- Old photos accessible via both old and new endpoints

### Phase 2: Android releases new version
- New version uses `/api/evidence/upload` for all new captures
- Supports video, voice, text, and campaign-free mode
- Old app versions continue working against old endpoint

### Phase 3: Migrate legacy data
- Background job: copy existing `photos` rows → `evidence` table
- Once verified, deprecate old endpoint (or keep as alias)

---

## Success Criteria

- [ ] User can capture video (30s) and it verifies correctly
- [ ] User can record voice note and it uploads with GPS context
- [ ] User can add text notes to any evidence
- [ ] User can capture without selecting a campaign
- [ ] Campaign locations can be created with just lat/lon (pin drop)
- [ ] 3rd party can call `/api/v1/verify` with API key and get a score
- [ ] Web dashboard shows all evidence types (photo/video/voice/text)
- [ ] Branding fetched from API and applied on Android

---

## References
- `WHITE_LABEL_ROADMAP.md` — detailed white-label phases
- `backend/app/models/` — current schema
- `backend/app/services/enhanced_verification.py` — verification pipeline
- `backend/app/api/bulk.py` — bulk upload (campaign-setup endpoint)
- Android: `app/build.gradle.kts` — current app configuration
- Android: `ui/theme/Color.kt`, `Theme.kt` — current theming
