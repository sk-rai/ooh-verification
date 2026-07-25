# TrustCapture Phase 2 Enhancements

## Status: PLANNED (After current Evidence Platform sprint)

Last updated: July 2026

---

## Overview

Phase 2 focuses on turning TrustCapture from a photo verification tool into a **complete field operations intelligence platform**. These enhancements unlock use cases across multiple industries: pipeline inspection, insurance surveys, delivery verification, workforce management, security patrols, agricultural surveys, and construction monitoring.

---

## Enhancement 1: Photo-to-Photo Distance & Route Analysis

### Problem
Clients need to verify that vendors actually covered the required area — not just visited one spot and uploaded all photos from there.

### Features

| Feature | Description |
|---------|-------------|
| Point-to-point distance | Haversine distance between any two evidence captures |
| Total route distance | Sum of sequential distances (chronological) per vendor per day |
| Coverage area | Convex hull of all photo GPS points — how much area was inspected |
| Gap detection | Flag when consecutive photos are too far apart (skipped area) or too close (not moving) |
| Impossible speed detection | Flag if distance/time ratio implies GPS spoofing (e.g., 50km in 5 minutes) |

### Backend Changes

| Component | Change | Effort |
|-----------|--------|--------|
| `GET /api/evidence/distance?id1=&id2=` | Return haversine distance between two captures | 0.5 day |
| `GET /api/campaigns/{id}/route-summary` | Total distance, coverage area, gaps, per vendor per day | 1-2 days |
| Verification pipeline | Add gap/speed flags to existing verification | 1 day |
| Haversine utility | Already exists in codebase | 0 |

### Frontend Changes

| Component | Change | Effort |
|-----------|--------|--------|
| Map View: route polyline | Connect photos chronologically per vendor with colored line | 2-3 days |
| Reports table: distance badge | "1.2 km from previous" next to each row | 0.5 day |
| Campaign detail: coverage summary | Total km, avg gap, max gap, coverage % | 1 day |
| Gap alerts | Visual markers on map where gaps > threshold | 1 day |

### Fraud Detection Signals

| Pattern | Meaning | Action |
|---------|---------|--------|
| All photos at same GPS (distance ≈ 0) | Vendor didn't move | Flag |
| 50km in 5 minutes between photos | GPS spoofing | Reject |
| Large gaps between consecutive photos | Missed inspection areas | Flag |
| Total distance << expected route length | Incomplete inspection | Flag |

---

## Enhancement 2: Passive GPS Tracking (Vendor Route Logging)

### Problem
Clients want to know vendors were actually in the field for the claimed hours, not just that they took photos at certain spots.

### Features

| Feature | Description |
|---------|-------------|
| Background GPS collection | Record vendor location every N minutes (configurable, default 30 min) |
| Max duration | Auto-stop after M hours (configurable, default 8 hours) or on app close |
| Periodic sync | Batch upload GPS points every sync interval |
| Daily route view | Map showing vendor's path throughout the day |
| Attendance dashboard | First ping, last ping, hours active, total km per vendor |

### Backend Changes

| Component | Change | Effort |
|-----------|--------|--------|
| `vendor_tracks` table | New table: track_id, vendor_id, date, points (JSONB), distance, duration | 0.5 day |
| `POST /api/tracks/sync` | Android sends batch of GPS points | 1 day |
| `GET /api/tracks/vendor/{id}?date=` | Get vendor's track for a day | 0.5 day |
| `GET /api/tracks/campaign/{id}?date=` | All vendor tracks for a campaign | 0.5 day |
| `GET /api/tracks/summary?date=` | Attendance summary: active vendors, hours, km | 1 day |
| App config: `tracking_config` section | enabled, interval, max_duration, sync_interval | 30 min |

### Frontend Changes

| Component | Change | Effort |
|-----------|--------|--------|
| Route map (per vendor per day) | Polyline with time-based coloring + photo markers | 2-3 days |
| Campaign coverage overlay | All vendor routes + campaign locations on same map | 2 days |
| Attendance table/dashboard | Vendor, start time, end time, hours, km, photos | 2 days |
| Gap detection visualization | Highlight periods with no data | 1 day |

### Android Changes

| Component | Change | Effort |
|-----------|--------|--------|
| Background location service | FusedLocationProvider + WorkManager | 2-3 days |
| Permission handling | `ACCESS_BACKGROUND_LOCATION` with rationale | 1 day |
| Sync manager | Batch upload points periodically | 1 day |
| Stop/pause controls | User can disable tracking from settings | 0.5 day |
| "My Route Today" screen | Vendor sees their own track | 1 day |

### Privacy & Compliance

- Opt-in with clear disclosure before enabling
- "Stop tracking" button always accessible
- Auto-stop after configured max hours
- Data retention: auto-delete after 90 days (configurable)
- Vendor can see their own data
- Play Store: declare `ACCESS_BACKGROUND_LOCATION` with justification

### Config Addition

```json
{
  "tracking_config": {
    "enabled": true,
    "interval_minutes": 30,
    "max_duration_hours": 8,
    "sync_interval_minutes": 30,
    "min_accuracy_meters": 100,
    "stop_on_app_close": true,
    "collect_battery_level": true
  }
}
```

---

## Enhancement 3: Expanded App Config

### Problem
Many Android behaviors are hardcoded. Moving them to backend config enables per-tenant customization and A/B testing without app updates.

### New Fields to Add to `GET /api/app/config`

**capture_config additions:**
```json
{
  "photo_max_dimension": 3000,
  "photo_compression_quality": 90,
  "max_text_note_length": 500,
  "allow_emulator_capture": true,
  "allow_rooted_capture": true,
  "watermark_opacity": 160,
  "watermark_height_percent": 15,
  "camera_facing": "back",
  "gps_interval_high_ms": 5000,
  "gps_interval_balanced_ms": 15000
}
```

**upload_config additions:**
```json
{
  "upload_timeout_photo_ms": 60000,
  "upload_timeout_video_ms": 90000,
  "wifi_only_upload": false,
  "upload_periodic_interval_minutes": 15
}
```

**ui_config additions:**
```json
{
  "features": {
    "campaigns": true,
    "quick_capture": true,
    "settings": true,
    "tracking": true
  },
  "maintenance": {
    "enabled": false,
    "message": ""
  }
}
```

### Per-Campaign Config

Add `config` JSONB column to campaigns table. Returned in `/api/vendors/me/campaigns`:

```json
{
  "config": {
    "max_video_duration_seconds": 30,
    "max_photos_per_location": 5,
    "photo_enabled": true,
    "video_enabled": true,
    "voice_note_enabled": false,
    "require_safety_tag": true,
    "multi_photo_required": true,
    "categories": ["billboard_installation"]
  }
}
```

If null/missing, Android uses global config.

### Backend Effort: 2-3 hours total

---

## Enhancement 4: 3rd Party API Integration

### Problem
External apps want TrustCapture as a verification layer without adopting the full platform.

### Features

| Feature | Description |
|---------|-------------|
| API key auth | Server-to-server authentication (no OTP/JWT needed) |
| Stateless verify endpoint | Send photo + GPS → get confidence score back |
| Webhook delivery | Notify their backend when verification completes |
| Rate limiting | Per API key, configurable |
| Usage tracking | Count calls per key per day for billing |

### Backend Changes

| Component | Change | Effort |
|-----------|--------|--------|
| `api_keys` table | key_id, client_id, key_hash, permissions, rate_limit | 1 day |
| API key auth middleware | Check `Authorization: Bearer tc_live_xxx` | 1 day |
| `POST /api/v1/verify` | Stateless verification (no campaign context) | 2-3 days |
| `POST /api/v1/webhooks` | Register callback URLs | 1 day |
| Rate limiting middleware | Per-key rate limiting | 1 day |
| Usage tracking | api_key_usage table, daily counts | 1 day |

### API Key Format
- Production: `tc_live_xxxxxxxxxxxxxxxx`
- Sandbox: `tc_test_xxxxxxxxxxxxxxxx`

### Verify Endpoint
```
POST /api/v1/verify
Authorization: Bearer tc_live_xxxxxxxx
Content-Type: multipart/form-data

Parts: file (photo), latitude, longitude, accuracy, expected_latitude (optional), expected_longitude (optional), tolerance_meters (optional)

Response: {
  "verification_id": "uuid",
  "confidence": 0.87,
  "status": "verified",
  "flags": [],
  "checks": {
    "location_match": {"score": 0.95, "passed": true},
    "freshness": {"score": 1.0, "passed": true}
  }
}
```

---

## Combined Phase 2 Timeline

### Week 1: Config + Distance

| Day | Backend | Android | Frontend |
|-----|---------|---------|----------|
| 1 | Expand app config (all new fields) | Read new config fields | — |
| 2 | Per-campaign config JSONB | Use per-campaign config | — |
| 3 | Distance endpoint + route summary | — | Route polyline on map |
| 4 | Gap/speed fraud flags in verification | — | Distance badges in reports |
| 5 | Testing + fixes | Testing | Coverage summary view |

### Week 2: Tracking + API

| Day | Backend | Android | Frontend |
|-----|---------|---------|----------|
| 1 | `vendor_tracks` table + sync endpoint | Background location service | — |
| 2 | Track query endpoints | Permission handling + sync manager | Route map view |
| 3 | `api_keys` table + auth middleware | Stop/pause controls | Attendance dashboard |
| 4 | `POST /api/v1/verify` stateless endpoint | "My Route Today" screen | Gap visualization |
| 5 | Webhooks + rate limiting | Testing | Campaign coverage overlay |

### Week 3: Polish + Documentation

| Day | Backend | Android | Frontend |
|-----|---------|---------|----------|
| 1 | Usage tracking + billing hooks | — | All views responsive |
| 2 | API documentation / developer portal | — | Testing |
| 3-5 | Integration testing, edge cases, deploy | Play Store update | Deploy |

---

## Industry Use Cases Unlocked by Phase 2

| Industry | Key Features Used |
|----------|-------------------|
| **Pipeline/Utilities** | Route tracking + coverage analysis + gap detection + asset_id locations |
| **Insurance** | Quick capture (no campaign) + before/after pairing + distance verification |
| **OOH Advertising** | Campaign route audit + photo-to-photo distance + attendance proof |
| **Construction** | Coverage area + multi-media evidence + progress tracking |
| **Delivery/Logistics** | Route tracking + impossible speed detection + delivery proof |
| **Security/Patrol** | Checkpoint distance verification + route logging + gap alerts |
| **Agriculture** | Coverage area (convex hull) + coordinate-only locations + GPS tracks |
| **Pharma/Medical Rep** | Field attendance + visit distance + route verification |
| **Telecom Tower Inspection** | Asset ID + coverage verification + route compliance |

---

## Dependencies & Decisions

| # | Decision | Options | Recommended |
|---|----------|---------|-------------|
| 1 | GPS tracking opt-in mechanism | Runtime permission + in-app toggle | Both |
| 2 | Track data retention | 30 / 60 / 90 / 365 days | 90 days default, configurable |
| 3 | Real-time tracking (live view) | WebSocket / polling | Polling (simpler, for v1) |
| 4 | API pricing model | Per-verification / monthly bundle | Monthly bundle with overage |
| 5 | Coverage calculation method | Convex hull / buffer union / grid-based | Convex hull (simplest) |

---

## References

- `PLATFORM_EVOLUTION_PLAN.md` — Current sprint (evidence platform)
- `WHITE_LABEL_ROADMAP.md` — Enterprise white-label phases
- `backend/app/api/evidence.py` — Evidence upload endpoint (current)
- `backend/app/api/app_config.py` — App config endpoint (current)
- `backend/app/services/enhanced_verification.py` — Verification pipeline
