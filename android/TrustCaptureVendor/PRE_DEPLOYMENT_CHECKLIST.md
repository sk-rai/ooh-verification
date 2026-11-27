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

## Combined Android test window

Defer phone testing until the configurable-forms candidate is ready. Test GPS in the same window. Track GPS, queued-media upgrade, and forms results separately in the release report. Record the candidate versionCode, artifact digest, test environment, and pass, fail, or pending status for each case.

The owner can run the routine GPS smoke test on their own phone using their own production test account. Use test routes. Keep fault injection and destructive test setup on an isolated local backend or mock. Run configurable-forms and Gate 1 upgrade tests in an approved isolated environment once their implementation is authorized.

## Gate 1 Android upgrade verification

**Status:** Play v15 baseline verified. The signed staging upgrade test is deferred to the combined Gate 1 and Gate 2 Play Internal testing window. The customer device inventory remains open. Production rollout remains on hold.

- Reviewed Android Room schema is **v13**, with registered migrations **10 → 11 → 12 → 13**. See [Gate 1 replay evidence](gate1-android-replay-evidence.md) for the reservation-specific client trace and WSL read-back.
- Staging emulator checks passed for OTP sign-in, device enrollment, package decode and rendering, and synthetic capture on Observation 2. Server read-back confirmed one receipt and evidence record for the normal sync and one for the controlled lost-response capture.
- The lost-response run force-stopped and reopened the app, then retried evidence alone after sign-in. The photo hash survived restart, and the replay acknowledgement was stored before local cleanup. The staging harness uses manual evidence sync.
- The offline cold-reopen run used airplane mode and Wi-Fi off after force-stop. It restored both measurements and the required photo slot on Observation 2 from the local cache without OTP. The offline view is read-only until sign-in.
- The side-by-side emulator APK has a separate application ID. Its checks do not prove a signed in-place upgrade of the Play v15 SQLCipher database. Test the complete migration chain to the combined candidate using the production application ID, a compatible Play signer, and a confirmed unused higher versionCode.

- Use the verified Play-generated universal APK for 1.5.0 (versionCode 15), package `com.lynksavvy.trustcapture`, as the provisional baseline. Offline inspection verified its signature and Room v10 in its packaged bytecode. APK SHA-256 is `a031f24540ebb1bf5c77edd7387ea338f068bf26cd1d4f492fa6c0904c3e48a8`. Signing certificate SHA-256 is `cb588df74b741fa54f0f977b5f48b2b55d4277c543e4637c4be555a19d67301f`. Record the candidate versionCode, artifact digest, and signing compatibility before testing. Add each older shipped baseline approved for direct upgrade after the customer device check.
- On an isolated staging device, install the signed baseline and use a synthetic account. Go offline and queue two distinct synthetic photos through the normal capture flow. Record each local queue ID, status, file path, and SHA-256. Confirm no staging evidence exists for the captures.
- While still offline, install the signed candidate in place without clearing app data. Confirm that both original queue IDs, statuses, and media hashes survive. Reconnect to staging and run the normal retry flow. Read back exactly one evidence record per capture and confirm both local items settle. Save the before/after evidence with the release report.

## Tracking sync acceptance for the next planned Android bundle

The Play-generated v15 APK confirms the field renames seen in the local AAB: `points` becomes `a`, and `lat`, `lon`, and `accuracy` become `a`, `b`, and `c`. Individual production 422s remain unattributed.

Verify the actual minified candidate's request JSON offline or against a local mock. It must have `points` containing objects with `lat`, `lon`, `accuracy`, and `timestamp_ms`, plus `battery_pct` when non-null. The debug regression tests cover the explicit wire names and null omission.

For the owner phone smoke test, sign in with the owner's test account and collect two distinct tracking batches. Confirm that the route appears and grows after the second sync. For a simple offline retry check, collect a batch with connectivity disabled, restore connectivity, and verify that the points appear. Record the account scope, candidate version, timestamps, and route result. Use the cases below for full acceptance and mark any assertion that the phone smoke test cannot establish as pending.

| Case | Procedure and expected evidence |
| --- | --- |
| Two successful batches | For one synthetic vendor and route day, send two distinct points in each batch, using unique timestamps and coordinates. After HTTP 200 for each batch, read the route back after the second response. Assert all four exact coordinates and timestamps persist and that the returned distance is nonzero and matches the fixture's independently calculated expectation within the backend's rounding tolerance. A successful response or count alone does not establish persistence. |
| Failed sync and recovery | Reject a request before server commit. Confirm the exact original points remain pending. Allow the retry to succeed and confirm only those acknowledged rows are marked synced. |
| Lost response after commit | In isolated staging, drop the response after verifying the server committed the first request. Confirm the client retains the pending rows, then allow a normal retry. Read the route back and record whether the same points or distance were counted twice. Escalate any duplication to release review. |
| In-place upgrade | Queue synthetic points offline on the signed baseline. Upgrade without clearing app data and compare local IDs, values, and pending status. Reconnect to staging and verify persistence and local settlement. |
| Midnight and delayed sync | Queue points with capture timestamps on either side of midnight and sync them together on a later receipt date. Record the capture timestamps, staging server timezone, receipt date, and route-history dates. Track capture-day grouping, timezone, and backfill as separate backend follow-up before promising historical recovery. |

Record any second-batch persistence failure or duplicate risk in the combined release report. Keep the GPS fix in the planned bundle. Publishing requires release approval.

## Configurable forms acceptance

- Assign a synthetic visit with one pinned form version, two repeated observations, and a required photo slot. Open the package online and confirm the expected form version and field controls.
- Go offline, enter both observations, and save a trusted photo against the second observation. Force-stop and reopen the app. Confirm that the pinned schema, answers, local capture ID, and photo binding survive.
- Restore connectivity. Verify that evidence uploads first, the draft binds the returned evidence ID to the second observation, and submission succeeds only after the backend accepts it. Confirm the accepted visit revision and status appear in the app and the photo appears on the correct observation.
- On the isolated backend, repeat with a lost evidence-upload response. Verify that retry resolves to one server evidence record and that the draft settles once. Exercise an unsupported required field or a stale edit revision and verify that the draft is preserved and submission is blocked or rejected with a usable message.

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
