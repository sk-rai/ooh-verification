# White-Label Integration Guide (Model 2: Deep Link SSO)

## Overview

This document describes how a client can integrate TrustCapture into their existing Android application without requiring vendors to sign in separately. The approach uses deep link / Intent-based SSO handoff — TrustCapture runs as its own app but accepts a pre-authenticated token from the host app, skipping the login screen entirely.

This is additive — existing standalone OTP login continues to work unchanged for all other users.

## Architecture

```
┌─────────────────────┐     server-to-server      ┌──────────────────────┐
│  Client Backend     │ ──────────────────────────▶│  TrustCapture API    │
│                     │  POST /api/auth/vendor/    │                      │
│                     │  token-exchange             │  Returns JWT         │
└────────┬────────────┘                            └──────────────────────┘
         │ JWT
         ▼
┌─────────────────────┐     deep link              ┌──────────────────────┐
│  Client Android App │ ──────────────────────────▶│  TrustCapture App    │
│                     │  trustcapture://auth?       │                      │
│                     │  token=xxx&tenant_id=yyy    │  Skips login,        │
│                     │  &vendor_id=zzz             │  goes to Campaigns   │
└─────────────────────┘                            └──────────────────────┘
```

## Auth Flow

```
Existing (standalone):
  LoginScreen → OTP → verify-otp → JWT saved to DataStore → Campaigns

New (SSO from host app):
  Host app backend → token-exchange (server-to-server) → gets TrustCapture JWT
  Host app → deep link with JWT → TrustCapture saves to DataStore → Campaigns
```

## Why This Doesn't Break Existing Users

- `AuthInterceptor` reads JWT from DataStore regardless of how it got there
- `TenantInterceptor` reads tenant ID from DataStore — same
- Upload pipeline, camera, sensors, signing — all downstream of auth — are unaffected
- OTP flow remains the default; deep link is an alternate entry path
- Device registration (StrongBox ECDSA) still happens on first deep-link login

## Android Changes Required

### 1. Intent Filter on MainActivity

Add to `AndroidManifest.xml`:

```xml
<activity android:name=".MainActivity">
    <!-- Existing launcher intent filter stays -->

    <!-- SSO deep link -->
    <intent-filter>
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data
            android:scheme="trustcapture"
            android:host="auth" />
    </intent-filter>
</activity>
```

### 2. Handle Deep Link in MainActivity.onCreate

```kotlin
// In onCreate, before setContent:
val uri = intent?.data
if (uri?.scheme == "trustcapture" && uri.host == "auth") {
    val token = uri.getQueryParameter("token")
    val tenantId = uri.getQueryParameter("tenant_id")
    val vendorId = uri.getQueryParameter("vendor_id")
    if (!token.isNullOrBlank() && !vendorId.isNullOrBlank()) {
        lifecycleScope.launch {
            userPreferences.saveAuthData(token, tenantId ?: "")
            userPreferences.saveVendorInfo(vendorId, "")
            // Device registration happens automatically on first API call
        }
    }
}
```

The existing `LaunchedEffect` in `setContent` already checks `isLoggedIn` and routes to Campaigns if a token exists — so this just works.

### 3. Register Device on First SSO Login

After deep link auth, the device won't have a registered ECDSA key yet. Add a check in `CampaignsViewModel.init` or a one-time startup hook:

```kotlin
// If logged in but device not registered, register now
if (authRepository.isDeviceRegistered().not()) {
    authRepository.registerDeviceIfNeeded()
}
```

This is a minor change — `registerDeviceIfNeeded()` is already implemented, just needs to be callable from outside `verifyOtp()`.

### 4. Optional: Return Result to Host App

If the host app needs to know when the vendor is done capturing:

```kotlin
// In CameraScreen, after successful capture + upload:
activity?.setResult(Activity.RESULT_OK, Intent().apply {
    putExtra("photos_captured", count)
    putExtra("campaign_code", campaignCode)
})
```

Host app launches with `startActivityForResult` or `ActivityResultLauncher`.

## Backend Changes Required (WSL Kiro)

### Token Exchange Endpoint

```
POST /api/auth/vendor/token-exchange
Headers:
  X-Partner-API-Key: <partner_api_key>
Body:
  {
    "vendor_id": "ABC123",
    "tenant_id": "uuid-of-tenant",
    "partner_id": "partner-identifier"
  }
Response:
  {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 604800
  }
```

Requirements:
- Partner API keys stored in a `partner_api_keys` table (partner_id, api_key_hash, tenant_id, created_at, is_active)
- Validate the API key belongs to the specified tenant
- Validate the vendor exists and is associated with the tenant
- Return a standard TrustCapture JWT (same format as OTP verify response)
- Audit log: record that login was via token-exchange, include partner_id
- Rate limit: 100 requests/min per partner key

### Partner Management

- Admin web UI or API to create/revoke partner API keys
- Each partner key is scoped to a single tenant
- Keys can be rotated without affecting existing sessions

## Deep Link URI Format

```
trustcapture://auth?token=<jwt>&tenant_id=<uuid>&vendor_id=<vendor_id>
```

| Parameter   | Required | Description                          |
|-------------|----------|--------------------------------------|
| token       | Yes      | JWT from token-exchange endpoint     |
| tenant_id   | No       | Tenant UUID (embedded in JWT too)    |
| vendor_id   | Yes      | 6-char vendor ID                     |

## Security Considerations

- The JWT is passed via deep link URI — this is visible in the Intent. On Android, only the launching app and TrustCapture can see it. No browser involved.
- Token exchange is server-to-server only. The partner's Android app never sees the API key — it gets the JWT from its own backend.
- JWTs from token-exchange should have the same expiry and claims as OTP-issued JWTs.
- Consider adding a `login_method: "token_exchange"` claim to the JWT for audit purposes.
- Deep link tokens should be single-use or short-lived (5 min) to prevent replay. The app saves it to DataStore immediately, so the URI doesn't need to persist.

## Effort Estimate

| Component                        | Effort    | Difficulty |
|----------------------------------|-----------|------------|
| Android: deep link handling      | 0.5 days  | Easy       |
| Android: device registration fix | 0.5 days  | Easy       |
| Android: result callback         | 0.5 days  | Easy       |
| Backend: token-exchange endpoint | 1 day     | Medium     |
| Backend: partner key management  | 1 day     | Medium     |
| Testing: end-to-end SSO flow    | 0.5 days  | Easy       |
| **Total**                        | **~3-4 days** |        |

## Future: Model 1 (SDK Embedding)

If a client needs TrustCapture's camera view embedded directly inside their own UI (no app switch), that requires extracting core logic into an Android library module. Key changes:

- Refactor from `@HiltAndroidApp` to `@EntryPoint` based DI
- Expose `TrustCaptureSDK.init(config)` and `TrustCaptureSDK.launchCapture(activity, campaignCode)`
- Namespace DataStore, Room DB, WorkManager to avoid collisions with host app
- Estimated effort: 2-3 weeks

Model 1 is deferred — Model 2 covers the integration use case with minimal risk.
