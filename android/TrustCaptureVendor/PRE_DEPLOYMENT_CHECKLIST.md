# Pre-Deployment Checklist (Play Store)

## Current Status: Waiting for Google Identity Verification (submitted 29 Mar 2026)

---

## Release Signing — CRITICAL

**Keystore file:** `android/TrustCaptureVendor/trustcapture-release.jks`
**Full path:** `C:\Users\SANTOSH\Documents\Photo_verification\android\TrustCaptureVendor\trustcapture-release.jks`
**Alias:** `trustcapture`
**Password (store + key):** `TrustCapture2026!`
**Algorithm:** RSA 2048-bit, validity 10,000 days
**DN:** `CN=LynkSavvy Technologies, OU=Mobile, O=LynkSavvy Technologies, L=Lucknow, ST=Uttar Pradesh, C=IN`

⚠️ **BACK THIS FILE UP IMMEDIATELY.** If lost, you can never update the app on Play Store.
⚠️ **Change the password** to something stronger and store in a password manager.
⚠️ File is in `.gitignore` — it will NOT be pushed to GitHub.

**Signing config location:** `local.properties` (also gitignored) contains:
```
RELEASE_STORE_FILE=trustcapture-release.jks
RELEASE_STORE_PASSWORD=TrustCapture2026!
RELEASE_KEY_ALIAS=trustcapture
RELEASE_KEY_PASSWORD=TrustCapture2026!
```

---

## Release AAB (Ready to Upload)

**File:** `app/build/outputs/bundle/release/app-release.aab`
**Size:** 12.82 MB
**Built:** 29 Mar 2026
**Version:** versionCode=1, versionName="1.0.0"

**To rebuild:**
```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
cmd /c "gradlew.bat bundleRelease 2>&1"
```

---

## Google Play Console

**Account:** LynkSavvy Technologies (Personal account)
**Console URL:** https://play.google.com/console
**Registration fee:** $25 USD (paid)
**Identity verification:** Submitted 29 Mar 2026 — waiting for approval (1-5 business days)
**D-U-N-S application:** Submitted (ref: DR032920262404761726) — for future Organization account migration

---

## Completed (Code-Side Prep)

- [x] ProGuard/R8 enabled — `isMinifyEnabled = true`, `isShrinkResources = true`, comprehensive keep rules in `proguard-rules.pro`
- [x] Debug Log.d statements removed from LoginViewModel, AuthRepository, UploadManager, UploadWorker, LocationHelper (Log.w/Log.e/Log.i kept)
- [x] Release signing config in `build.gradle.kts` — reads from `local.properties`
- [x] Release keystore generated and AAB built successfully
- [x] Version scheme set — versionCode=1, versionName="1.0.0"
- [x] Custom app icon — shield with camera lens + green verification checkmark (replaces default Android robot)
- [x] Certificate pinning framework in place (placeholder pins — replace before production domain switch)
- [x] `android:usesCleartextTraffic` restricted to debug builds only
- [x] Hybrid auth (StrongBox/TEE ECDSA challenge-response)
- [x] Atomic logout (single DataStore transaction)
- [x] OkHttp logging at HEADERS level (not BODY)
- [x] Country code auto-detection from SIM/locale
- [x] WorkManager background sync
- [x] Battery optimization (adaptive GPS power modes)
- [x] Error handling polish
- [x] Settings screen

---

## Remaining — After Google Verification Approves

### Play Store Listing (in Play Console)
- [ ] Short description (80 chars max)
- [ ] Full description (4000 chars max)
- [ ] App icon upload (512x512 PNG — generate from the vector drawable)
- [ ] Feature graphic (1024x500 PNG)
- [ ] Phone screenshots (minimum 2, recommended 4-8)
- [ ] Privacy policy URL (host on website or GitHub Pages)
- [ ] Data safety section declaration (location, camera, phone state, network)
- [ ] Content rating questionnaire
- [ ] Select app category: Business or Productivity
- [ ] Target audience: 18+ (business tool)
- [ ] Upload AAB to internal/closed testing track first, then promote to production

### Optional Before Launch
- [ ] Replace placeholder certificate pins with real SHA-256 fingerprints (when switching to production domain)
- [ ] Play Integrity API (requires Google Cloud project + API key)
- [ ] Generate raster mipmap PNGs from vector icon for pre-API-26 devices
- [ ] Test release build on physical device (verify ProGuard didn't break anything)

---

## Build Commands Reference

```powershell
# Set Java home (required before any Gradle command)
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"

# Debug APK (for testing)
cmd /c "gradlew.bat assembleDebug 2>&1"
# Output: app/build/outputs/apk/debug/app-debug.apk

# Release AAB (for Play Store)
cmd /c "gradlew.bat bundleRelease 2>&1"
# Output: app/build/outputs/bundle/release/app-release.aab

# Release APK (for sideloading)
cmd /c "gradlew.bat assembleRelease 2>&1"
# Output: app/build/outputs/apk/release/app-release.apk
```

All commands run from: `android/TrustCaptureVendor/`
