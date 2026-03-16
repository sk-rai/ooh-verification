# Pre-Deployment Checklist (Play Store)

Items deferred during development that must be completed before Play Store release.

## Security & Integrity
- [ ] Task 49.2: Play Integrity API (replaces deprecated SafetyNet) — requires Google Cloud project + API key
- [x] Certificate pinning for production API endpoint — OkHttp CertificatePinner + network_security_config.xml added. Placeholder SHA-256 pins need replacing with real cert fingerprints before release.
- [ ] Switch BASE_URL from `http://10.0.2.2:8000` to production HTTPS endpoint (already configured in release buildType)
- [ ] Replace placeholder certificate pins in `NetworkModule.kt` and `network_security_config.xml` with actual SHA-256 fingerprints
- [ ] ProGuard/R8 code obfuscation enabled in release build
- [x] `android:usesCleartextTraffic` restricted to debug builds only via manifest placeholder
- [x] `network_security_config.xml` enforces HTTPS-only for release, cleartext only for debug emulator

## Signing & Release
- [ ] Generate production signing keystore (upload key for Play App Signing)
- [ ] Configure release build type with signing config
- [ ] Set proper versionCode/versionName scheme

## Permissions
- [ ] Task 35.2: Permission rationale dialogs (explain why camera/location/phone needed)
- [ ] Task 35.3: Handle "Don't ask again" → direct to app settings
- [ ] Background location permission (separate from foreground) if needed for sync

## Missing Features
- [x] Task 51.7: Settings screen (logout, WiFi-only upload, clear cache, app version) — done
- [x] Task 53: Battery optimization (GPS power management, low-power mode when camera inactive) — done
- [x] Task 54: Error handling polish (user-friendly error messages, retry dialogs) — done
- [ ] Task 55.1 (partial): Delivery campaign signature capture — Canvas-based touch drawing pad for recipient signature (Req 18.3). Deferred pending user demand. Requires: signature composable, PNG export, upload as separate file, backend storage.
- [ ] WorkManager for background sync (currently upload only triggers on capture + screen load)

## Testing
- [ ] Property-based tests (tasks 35.3, 38.2, 38.6, 39.3, 42.2-42.4, 43.2, 45.2, 46.3-46.5)
- [ ] UI tests (task 51.8)
- [ ] End-to-end integration test on physical device
- [ ] Test on multiple screen sizes and Android versions (API 24-34)

## Store Listing
- [ ] App icon (proper adaptive icon, not default)
- [ ] Screenshots for Play Store listing
- [ ] Privacy policy URL (required by Play Store)
- [ ] Data safety section declaration (location, camera, phone state, network)
- [ ] Content rating questionnaire
