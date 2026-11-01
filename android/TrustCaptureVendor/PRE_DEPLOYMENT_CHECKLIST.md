# Pre-Deployment Checklist (Play Store)

## Current Status: LIVE on Production

- **Google identity verification:** Approved (account active).
- **Current production release:** versionCode 15 / versionName 1.5.0 — LIVE on Google Play since 31 Oct 2026, 4:46 PM. See `RELEASE_NOTES_1.5.0.md`.
  - Device key-lifecycle fix: key regeneration detection + OTP re-registration gate + server-side key versioning (commit f097adb on server, commit c2bba54 on Android).
  - Merged from branch `fix/device-key-lifecycle` → main.
- **Previous production releases:** vc14 (1.4.1) → vc11 (1.3.0) → ...
- **Version-code history:** vc11 live→14 live→15 live. vc12/13 consumed by earlier upload attempts. Always confirm next free code in Play Console before building.
- **App signing:** Google Play App Signing in use; local keystore is the upload key.

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
**Size:** 16.56 MB
**Built:** 18 Oct 2026
**Version:** versionCode=14, versionName="1.4.1"
**target/compileSdk:** 36 (Android 16) — AGP bumped 8.7.3 → 8.10.0 to support it
**Native debug symbols:** included (`ndk { debugSymbolLevel = "FULL" }` in release buildType)
**Signature:** `jar verified` (self-signed upload key — correct for Play App Signing)

**To rebuild:**
```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
cmd /c "gradlew.bat bundleRelease 2>&1"
```

> **Build gotcha (seen 18 Oct 2026):** a `clean` interrupted mid-run left `app/build`
> in a bad state and spawned duplicate Kotlin daemons, causing
> `[ksp] [Hilt] failed to make parent directories`. Fix: `gradlew.bat --stop`,
> delete `app/build`, then `gradlew.bat bundleRelease --no-daemon`.

---

## Google Play Console

**Account:** LynkSavvy Technologies (Personal account)
**Console URL:** https://play.google.com/console
**Registration fee:** $25 USD (paid)
**Identity verification:** Approved — account active, app published.
**D-U-N-S application:** Submitted (ref: DR032920262404761726) — for future Organization account migration

### Open recommendations on current release (vc11 / 1.3.0) — non-blocking
- Edge-to-edge may not display for all users (deprecated APIs/params) — future code change.
- R8 optimization — already enabled in vc12 build; should clear on next release.

---

## Completed (Code-Side Prep)

- [x] ProGuard/R8 enabled — `isMinifyEnabled = true`, `isShrinkResources = true`, comprehensive keep rules in `proguard-rules.pro`
- [x] Debug Log.d statements removed from LoginViewModel, AuthRepository, UploadManager, UploadWorker, LocationHelper (Log.w/Log.e/Log.i kept)
- [x] Release signing config in `build.gradle.kts` — reads from `local.properties`
- [x] Release keystore generated and AAB built successfully
- [x] Version scheme — currently versionCode=12, versionName="1.4.0" (production live at vc11/1.3.0)
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

## Store Listing (completed at initial launch — app is live)

- [x] Short description, full description
- [x] App icon (512x512), feature graphic (1024x500), phone screenshots
- [x] Privacy policy URL
- [x] Data safety declaration (location, camera, phone state, network)
- [x] Content rating questionnaire
- [x] App category + target audience (18+ business tool)

---

## Per-Release Upload Process (repeat for each new version)

1. Bump `versionCode` (and `versionName` if appropriate) in `app/build.gradle.kts`.
   - **Rule:** the new `versionCode` MUST be greater than the highest code uploaded
     to ANY track. Production is currently vc11; the next upload is vc12.
2. Build the signed AAB (see "Release AAB" section above).
3. Verify version + signature before upload:
   ```powershell
   $env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
   & "$env:JAVA_HOME\bin\jarsigner.exe" -verify app\build\outputs\bundle\release\app-release.aab
   ```
4. Play Console → upload to internal/closed testing first, then promote to Production.
5. Paste release notes (see `RELEASE_NOTES_<version>.md`).

### vc14 / 1.4.1 — PUBLISHED
- [x] Code at vc14 / 1.4.1, targetSdk/compileSdk = 36 (AGP 8.10.0)
- [x] Signed AAB built & verified (18 Oct 2026, native debug symbols included)
- [x] Release notes drafted — `RELEASE_NOTES_1.4.1.md`
- [x] Uploaded to internal testing, verified
- [x] Background-location + foreground-service declarations approved
- [x] Rolled out to Production (100%) — LIVE since 21 Oct 2026

> Version-code history: vc11 = live Production (1.3.0). vc12 (API 35) and vc13
> were consumed by earlier upload attempts and can never be reused. vc14 is the
> current uploadable build. Before any future build, check Play Console for the
> next free version code.

## Still Optional / Future
- [ ] Replace placeholder certificate pins with real SHA-256 fingerprints
- [ ] Play Integrity API (requires Google Cloud project + API key)
- [ ] Generate raster mipmap PNGs from vector icon for pre-API-26 devices
- [ ] Address edge-to-edge deprecation (Play Console recommendation on vc11)

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
