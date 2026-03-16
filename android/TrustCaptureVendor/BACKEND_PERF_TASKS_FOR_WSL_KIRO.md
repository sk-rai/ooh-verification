# Performance Optimization Tasks for WSL Kiro (Tasks 62.1 + 62.2)

## Context
Phase 3 (Android) and Task 61.3 (Android↔backend wiring + certificate pinning) are complete. The Android Kiro session is handling Task 62.3 (Android performance). This document covers the backend (62.1) and web app (62.2) performance tasks for the WSL Kiro session.

Reference: `.kiro/specs/trust-capture/tasks.md` lines ~1230-1270

---

## Task 62.1: Backend Performance Optimizations

### 62.1.1 Database Query Indexes (Priority: High)

The following tables need indexes for common query patterns. Create an Alembic migration.

```sql
-- Photos: queried by campaign, vendor, status, timestamp
CREATE INDEX ix_photos_campaign_id ON photos(campaign_id);
CREATE INDEX ix_photos_vendor_id ON photos(vendor_id);
CREATE INDEX ix_photos_verification_status ON photos(verification_status);
CREATE INDEX ix_photos_captured_at ON photos(captured_at DESC);
CREATE INDEX ix_photos_campaign_status ON photos(campaign_id, verification_status);

-- Audit logs: queried by entity, action, timestamp
CREATE INDEX ix_audit_logs_entity_type ON audit_logs(entity_type);
CREATE INDEX ix_audit_logs_entity_id ON audit_logs(entity_id);
CREATE INDEX ix_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX ix_audit_logs_action ON audit_logs(action);

-- Campaign vendor assignments: queried by vendor and campaign
CREATE INDEX ix_campaign_vendor_assignments_vendor_id ON campaign_vendor_assignments(vendor_id);
CREATE INDEX ix_campaign_vendor_assignments_campaign_id ON campaign_vendor_assignments(campaign_id);

-- Location profiles: queried by campaign location
CREATE INDEX ix_location_profiles_campaign_location_id ON location_profiles(campaign_location_id);

-- Sensor data: queried by photo
CREATE INDEX ix_sensor_data_photo_id ON sensor_data(photo_id);

-- Vendors: queried by tenant and phone
CREATE INDEX ix_vendors_tenant_id ON vendors(tenant_id);
CREATE INDEX ix_vendors_phone ON vendors(phone);

-- Campaigns: queried by tenant and client
CREATE INDEX ix_campaigns_tenant_id ON campaigns(tenant_id);
CREATE INDEX ix_campaigns_client_id ON campaigns(client_id);
CREATE INDEX ix_campaigns_status ON campaigns(status);
```

Check existing indexes first (`\di` in psql) to avoid duplicates. SQLAlchemy models may already have `index=True` on some columns.

### 62.1.2 Database Connection Pooling (Priority: Medium)

Already partially done in `backend/app/core/database.py`:
- `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True` are set
- These are configurable via env vars `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW`

Add these improvements:
```python
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DEBUG", "False").lower() == "true",
    pool_size=int(os.getenv("DATABASE_POOL_SIZE", "20")),
    max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
    pool_pre_ping=True,
    pool_recycle=3600,        # Recycle connections after 1 hour
    pool_timeout=30,          # Wait max 30s for a connection from pool
    pool_use_lifo=True,       # LIFO reuse = fewer idle connections
)
```

### 62.1.3 Redis Caching (Priority: High)

`redis` and `aioredis` are already in `requirements.txt`. `REDIS_URL` is in `.env.example`.

Create `backend/app/core/redis.py`:
```python
import redis.asyncio as redis
import os
import json
from typing import Optional

_redis_client: Optional[redis.Redis] = None

async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True
        )
    return _redis_client

async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
```

Add `close_redis()` to the shutdown event in `main.py`.

Cache these hot paths:
1. **Vendor campaigns list** (`GET /api/vendors/me/campaigns`) — cache per vendor_id, TTL 5 min
2. **Campaign details** — cache per campaign_id, TTL 10 min
3. **Subscription status** — cache per tenant_id, TTL 15 min
4. **Location profiles** — cache per campaign_location_id, TTL 30 min (rarely changes)

Invalidate cache on writes (campaign update, assignment change, subscription change).

Example pattern for vendor campaigns:
```python
async def get_vendor_campaigns_cached(vendor_id: int, db: AsyncSession, r: redis.Redis):
    cache_key = f"vendor:{vendor_id}:campaigns"
    cached = await r.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # DB query
    campaigns = await fetch_vendor_campaigns(vendor_id, db)
    await r.setex(cache_key, 300, json.dumps(campaigns))  # 5 min TTL
    return campaigns
```

### 62.1.4 Streaming Photo Upload (Priority: Medium)

Current `backend/app/api/photos.py` reads the entire file into memory via `await file.read()`. For large photos this is fine (5MB limit), but for efficiency:

```python
# Instead of: photo_bytes = await file.read()
# Use streaming to S3:
import io

async def stream_upload_to_s3(file: UploadFile, s3_key: str):
    """Stream file directly to S3 without loading entirely into memory."""
    chunks = []
    async for chunk in file:
        chunks.append(chunk)
    content = b"".join(chunks)
    # Still need full bytes for hash/signature verification,
    # but this pattern allows future chunked processing
    return content
```

For the current 5MB limit, the memory impact is minimal. This becomes important if you increase the limit or add video support later. Lower priority.

### 62.1.5 API Response Compression (Priority: High, Easy)

Add GZip middleware to `main.py`. This compresses all responses > 500 bytes:

```python
from fastapi.middleware.gzip import GZipMiddleware

# Add BEFORE CORS middleware
app.add_middleware(GZipMiddleware, minimum_size=500)
```

This is a one-liner that significantly reduces payload sizes for JSON responses and photo metadata.

---

## Task 62.2: Web Application Performance Optimizations

Tech stack: React 18 + Vite + TailwindCSS + React Query + React Router

### 62.2.1 Code Splitting and Lazy Loading (Priority: High)

In `web/src/App.tsx`, convert page imports to lazy imports:

```tsx
import { lazy, Suspense } from 'react';

// Replace direct imports with lazy
const Dashboard = lazy(() => import('./pages/dashboard/Dashboard'));
const Login = lazy(() => import('./pages/auth/Login'));
const AdminPanel = lazy(() => import('./pages/admin/AdminPanel'));
// ... etc for all page components

// Wrap routes in Suspense
<Suspense fallback={<LoadingSpinner />}>
  <Routes>
    <Route path="/dashboard" element={<Dashboard />} />
    ...
  </Routes>
</Suspense>
```

Vite automatically code-splits lazy imports into separate chunks.

### 62.2.2 Image Lazy Loading (Priority: Medium)

For photo grids (campaign photos, verification photos), use native lazy loading:

```tsx
<img src={photoUrl} loading="lazy" alt="..." />
```

For more control, use Intersection Observer:
```tsx
function LazyImage({ src, alt }: { src: string; alt: string }) {
  const ref = useRef<HTMLImageElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setIsVisible(true);
        observer.disconnect();
      }
    });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return <img ref={ref} src={isVisible ? src : ''} alt={alt} loading="lazy" />;
}
```

### 62.2.3 React Query Optimization (Priority: Medium)

Already using `@tanstack/react-query`. Ensure these settings:

```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,    // 5 min before refetch
      gcTime: 30 * 60 * 1000,       // 30 min cache retention
      refetchOnWindowFocus: false,   // Don't refetch on tab switch
      retry: 2,
    },
  },
});
```

### 62.2.4 Virtual Scrolling for Large Lists (Priority: Low)

If campaign or photo lists exceed ~100 items, add `@tanstack/react-virtual`:

```bash
npm install @tanstack/react-virtual
```

Apply to photo grids and campaign lists. Only render visible rows.

### 62.2.5 Bundle Size Optimization (Priority: Medium)

1. Check current bundle: `npx vite-bundle-visualizer`
2. `plotly.js` is huge (~3.5MB). Switch to partial bundle:
   ```bash
   npm install plotly.js-basic-dist-min
   ```
3. `mapbox-gl` is also large. Consider loading it dynamically only on map pages.
4. Add to `vite.config.ts`:
   ```ts
   build: {
     rollupOptions: {
       output: {
         manualChunks: {
           vendor: ['react', 'react-dom', 'react-router-dom'],
           charts: ['plotly.js-basic-dist-min', 'react-plotly.js'],
           maps: ['mapbox-gl', 'react-map-gl'],
         }
       }
     }
   }
   ```

### 62.2.6 Service Worker for Offline Support (Priority: Low)

Use `vite-plugin-pwa`:
```bash
npm install -D vite-plugin-pwa
```

Configure in `vite.config.ts` for caching static assets. The web app is primarily for admin/client use, so offline support is nice-to-have, not critical.

---

## Task 61.1: Wire Backend Services Together (if not already done)

Check that these flows work end-to-end:
1. Auth → all protected endpoints use JWT middleware
2. Photo upload → triggers verification workflow (signature check, location match, sensor comparison)
3. Location matching → updates verification status on photo record
4. Audit logging → all photo captures and status changes logged
5. Subscription checking → upload endpoints enforce quota limits

Most of this should already be wired from earlier phases. Verify and fix any gaps.

## Task 61.2: Wire Web App to Backend (if not already done)

1. All API calls use the configured base URL
2. JWT token refresh logic (intercept 401, refresh, retry)
3. Graceful error handling (toast notifications, error boundaries)
4. Loading states on all async operations (React Query handles most of this)

---

## Completion Criteria

After completing these tasks, mark in `.kiro/specs/trust-capture/tasks.md`:
- `[x] 62.1` with sub-items
- `[x] 62.2` with sub-items
- `[x] 61.1` if verified/fixed
- `[x] 61.2` if verified/fixed

The Android Kiro session will handle `[x] 62.3` independently.
