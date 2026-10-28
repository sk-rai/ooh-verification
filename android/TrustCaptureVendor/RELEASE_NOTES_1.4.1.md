# Release Notes — TrustCapture Vendor 1.4.1 (versionCode 14)

**Status:** LIVE on Google Play Production since 21 Oct 2026 (100% rollout).
**Previous production release:** 1.3.0 (versionCode 11)
**Package:** `com.lynksavvy.trustcapture`
**Build date:** 18 Oct 2026
**AAB:** `app/build/outputs/bundle/release/app-release.aab` (16.56 MB, signed, native debug symbols included)
**targetSdk / compileSdk:** 36 (Android 16) — required by Play Console

> Version-code note: vc12 / 1.4.0 was built but failed Play Console's "must
> target API 36" check. vc13 was consumed by a subsequent upload attempt. The
> shipped build is **vc14**, which raises targetSdk to 36 (AGP 8.7.3 → 8.10.0).
> Feature set is identical to the intended 1.4.0 plus the API-36 target.

---

## Play Store "What's new" (short — paste into the release)

Keep under 500 characters per language. Suggested text:

```
• New My Route Today screen — see your day's verified activity: points, duration, and distance.
• New Settings screen with a tracking on/off toggle you control.
• Smarter capture: campaigns now show only the evidence types they allow (photo, video, voice, text).
• More reliable multi-location campaigns — capture now matches the nearest valid site.
• Updated for Android 16 (API 36); stability and performance improvements.
```

---

## Full changelog (1.3.0 → 1.4.0)

### New features
- **My Route Today screen** — vendors can review the day's activity (points, duration, distance), synced from the backend. (`fa2670e`)
- **Settings screen** — includes a vendor-controlled background-tracking toggle. (`fa2670e`)
- **Background GPS tracking** — optional background location service with a dedicated sync worker and an explicit background-location permission request. (`c6eea3e`)
- **Per-campaign evidence config** — the app now hides video, voice, or text capture options based on each campaign's configuration, so vendors only see what a campaign allows. (`4f8466b`)

### Fixes & improvements
- **Multi-location campaigns** now match the closest valid location instead of only the first, which previously rejected valid captures. (`2b1e6e3`)
- **Route map auto-fit** — the map now fits to the selected vendor route. (`e1f2e8b`)

### Backend / platform (supports the app, not user-visible in the app)
- `GET /api/tracks/me` endpoint with geofence verification (bbox / polygon / corridor). (`1d37270`)
- Data-isolation fix: photos/reports scoped by `client_id`. (`c62b3e0`)
- Maintenance mode disabled in live app config. (`9e91340`)

---

## Known advisories from Play Console (non-blocking for this release)
- **Edge-to-edge deprecation** — flagged on 1.3.0. Requires a code change in a future release; not addressed in 1.4.0.
- **R8 optimization** — already enabled in this build (`isMinifyEnabled`, `isShrinkResources`), so this recommendation should clear.

---

## Upload steps (manual, in Play Console)
1. play.google.com/console → TrustCapture → choose a track (internal/closed testing first is recommended, then promote to Production).
2. Create new release → upload `app-release.aab`.
3. Paste the "What's new" text above.
4. Review → roll out.
