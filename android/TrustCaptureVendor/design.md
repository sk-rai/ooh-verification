# Design Document: Android Vendor Application — Phase 1 (Core MVP)

## Overview

Phase 1 delivers a working Android app that allows vendors to log in via OTP, view assigned campaigns, capture photos with GPS data, and upload them to the TrustCapture backend. The app targets Android 7.0 (API 24) as minimum SDK for broadest device coverage while supporting modern Jetpack libraries.

## Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Language | Kotlin 1.9+ | Modern, concise, official Android language |
| UI | Jetpack Compose + Material 3 | Declarative UI, less boilerplate |
| Min SDK | API 24 (Android 7.0 Nougat) | ~97% device coverage, supports all required APIs |
| Target SDK | API 34 (Android 14) | Latest stable, required for Play Store |
| Networking | Retrofit 2 + OkHttp 4 | Industry standard, interceptors for auth |
| JSON | Kotlinx Serialization | Kotlin-native, compile-time safe |
| Image Loading | Coil 2 | Kotlin-first, Compose-native, lightweight |
| Camera | CameraX | Simplified camera API, lifecycle-aware |
| Location | Google Play Services Location | Fused location provider, best accuracy |
| DI | Hilt (Dagger) | Official Android DI, Compose integration |
| Navigation | Jetpack Navigation Compose | Type-safe navigation, deep linking |
| Local Storage | Room + DataStore | Room for structured data, DataStore for preferences |
| Security | Android Keystore + EncryptedSharedPreferences | Hardware-backed key storage |
| Build | Gradle 8.x + AGP 8.x | Latest stable Android build tools |

## Architecture

### MVVM + Clean Architecture (simplified)

```
┌─────────────────────────────────────────────┐
│                   UI Layer                   │
│  Compose Screens → ViewModels → UI State     │
├─────────────────────────────────────────────┤
│                Domain Layer                  │
│  Use Cases (optional for Phase 1)            │
├─────────────────────────────────────────────┤
│                 Data Layer                   │
│  Repositories → Remote (API) + Local (Room)  │
├─────────────────────────────────────────────┤
│              Framework Layer                 │
│  Camera, Location, Sensors, Keystore         │
└─────────────────────────────────────────────┘
```

### Package Structure

```
com.trustcapture.vendor/
├── TrustCaptureApp.kt              # Application class + Hilt entry point
├── MainActivity.kt                  # Single activity, Compose host
├── di/                              # Hilt modules
│   ├── NetworkModule.kt             # Retrofit, OkHttp
│   ├── DatabaseModule.kt            # Room database
│   └── AppModule.kt                 # App-level dependencies
├── data/
│   ├── remote/
│   │   ├── api/
│   │   │   ├── AuthApi.kt           # Auth endpoints
│   │   │   ├── CampaignApi.kt       # Campaign endpoints
│   │   │   └── PhotoApi.kt          # Photo upload endpoint
│   │   ├── dto/                     # API request/response models
│   │   └── interceptor/
│   │       └── AuthInterceptor.kt   # JWT token injection
│   ├── local/
│   │   ├── db/
│   │   │   ├── AppDatabase.kt       # Room database
│   │   │   ├── CampaignDao.kt       # Campaign queries
│   │   │   └── PhotoDao.kt          # Photo queue queries
│   │   ├── entity/                  # Room entities
│   │   └── datastore/
│   │       └── UserPreferences.kt   # Auth token, settings
│   └── repository/
│       ├── AuthRepository.kt
│       ├── CampaignRepository.kt
│       └── PhotoRepository.kt
├── ui/
│   ├── navigation/
│   │   └── NavGraph.kt              # Navigation routes
│   ├── theme/
│   │   ├── Theme.kt                 # Material 3 theme
│   │   ├── Color.kt
│   │   └── Type.kt
│   ├── auth/
│   │   ├── LoginScreen.kt           # Phone + Vendor ID input
│   │   ├── OtpScreen.kt             # OTP verification
│   │   └── AuthViewModel.kt
│   ├── campaigns/
│   │   ├── CampaignListScreen.kt    # Campaign list
│   │   ├── CampaignDetailScreen.kt  # Campaign details + capture button
│   │   └── CampaignViewModel.kt
│   ├── capture/
│   │   ├── CameraScreen.kt          # Camera preview + capture
│   │   ├── PhotoPreviewScreen.kt    # Review before save
│   │   └── CaptureViewModel.kt
│   └── common/
│       ├── ConnectivityBanner.kt    # Online/offline indicator
│       ├── LoadingIndicator.kt
│       └── ErrorDialog.kt
├── service/
│   ├── LocationService.kt           # Fused location provider
│   └── ConnectivityMonitor.kt       # Network state observer
└── util/
    ├── PermissionHelper.kt          # Runtime permission handling
    ├── PhotoCompressor.kt           # JPEG compression
    └── Constants.kt                 # API base URL, config
```

## API Integration

### Backend Endpoints Used (Phase 1)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/vendor/request-otp` | POST | Send OTP to vendor phone |
| `/api/auth/vendor/verify-otp` | POST | Verify OTP, get JWT token |
| `/api/auth/vendor/register-device` | POST | Register device + public key |
| `/api/auth/vendor/challenge` | POST | Get challenge nonce for device auth |
| `/api/auth/vendor/device-login` | POST | Verify ECDSA signature, get JWT |
| `/api/vendors/{id}/campaigns` | GET | Get assigned campaigns |
| `/api/campaigns/{id}` | GET | Get campaign details |
| `/api/photos` | POST | Upload photo with metadata |

### Auth Flow

The app uses a hybrid authentication model:
- **First login**: SMS OTP (via Twilio) + device registration (ECDSA public key)
- **Subsequent logins**: Device attestation via StrongBox/TEE ECDSA challenge-response (no SMS needed)

```
Vendor enters vendor_id
        │
        ▼
  Is device registered?
     ┌──────┴──────┐
    YES             NO
     │               │
     ▼               ▼
POST /challenge   Vendor enters phone number
     │               │
     ▼               ▼
Sign challenge    POST /request-otp
with StrongBox       │
ECDSA key            ▼
     │            Vendor enters OTP from SMS
     ▼               │
POST /device-login   ▼
     │            POST /verify-otp (with device_id)
     ▼               │
Receive JWT          ▼
     │            Receive JWT → generate ECDSA key pair
     ▼               │
Navigate to          ▼
Campaign List    POST /register-device (public key PEM)
                     │
                     ▼
                 Save device_registered flag
                     │
                     ▼
                 Navigate to Campaign List
```

**Device attestation endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/vendor/challenge` | POST | Get random 64-char hex nonce (5min TTL) |
| `/api/auth/vendor/device-login` | POST | Verify ECDSA signature, return JWT |

**Key details:**
- Algorithm: ECDSA P-256 (secp256r1), SHA256withECDSA
- Key storage: Android Keystore with StrongBox (falls back to TEE)
- Challenge: 64-char hex string signed as UTF-8 bytes
- Signature format: Base64-encoded DER
- On logout, `device_registered` flag and vendor ID are preserved (Keystore key survives logout)
- On 401 (key mismatch), flag is reset and user falls back to OTP

### Auth Interceptor

OkHttp interceptor automatically adds `Authorization: Bearer <token>` to all API requests. On 401 response, clears token and navigates to login.

### Emulator → WSL Backend Connectivity

The Android emulator maps `10.0.2.2` to the host machine's `localhost`. Since the backend runs in WSL on port 8000, the app uses:

```
BASE_URL = "http://10.0.2.2:8000"
```

For physical devices on the same WiFi, use the machine's LAN IP instead.

## Data Models

### Room Entities

```kotlin
@Entity(tableName = "campaigns")
data class CampaignEntity(
    @PrimaryKey val campaignId: String,
    val campaignCode: String,
    val name: String,
    val campaignType: String,
    val status: String,
    val startDate: String,
    val endDate: String,
    val lastSynced: Long
)

@Entity(tableName = "photo_queue")
data class PhotoEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val campaignId: String,
    val campaignCode: String,
    val localFilePath: String,
    val thumbnailPath: String?,
    val latitude: Double,
    val longitude: Double,
    val accuracy: Float,
    val altitude: Double?,
    val capturedAt: Long,
    val uploadStatus: String,  // pending, uploading, uploaded, failed
    val retryCount: Int = 0,
    val errorMessage: String? = null
)
```

### API DTOs

```kotlin
@Serializable
data class OtpRequest(val vendorId: String, val phoneNumber: String)

@Serializable
data class OtpVerify(val vendorId: String, val phoneNumber: String, val otp: String)

@Serializable
data class DeviceRegister(val deviceId: String, val publicKey: String)

@Serializable
data class CampaignResponse(
    val campaignId: String, val campaignCode: String,
    val name: String, val campaignType: String,
    val status: String, val startDate: String, val endDate: String
)

@Serializable
data class PhotoUploadResponse(val photoId: String, val status: String)
```

## Camera Implementation

Using CameraX with ImageCapture use case:

1. Preview: bound to Compose `AndroidView` wrapping `PreviewView`
2. Capture: `ImageCapture.takePicture()` saves to app-private storage
3. Post-capture: compress to max 5MB, extract GPS from EXIF
4. Location is captured independently via FusedLocationProviderClient at capture time (not from EXIF, which may be stripped)

## Location Strategy

- Use `FusedLocationProviderClient` with `PRIORITY_HIGH_ACCURACY`
- Request location update when camera screen opens
- Capture latest location at photo capture moment
- Display accuracy to vendor; warn if > 50m
- Location permission: request `ACCESS_FINE_LOCATION` at point of use (camera screen)

## Connectivity Monitoring

- Use `ConnectivityManager.NetworkCallback` for real-time network state
- Expose as `StateFlow<Boolean>` from `ConnectivityMonitor`
- UI shows persistent banner when offline
- Photo upload checks connectivity before attempting

## Permission Flow

Permissions requested at point of use, not on app launch:
1. Camera → requested when vendor taps "Capture Photo"
2. Location → requested when camera screen opens
3. Storage → not needed on API 29+ (scoped storage), requested on older devices

Each permission shows rationale dialog before system prompt.

## Error Handling Strategy

- API errors: parsed from response body, displayed as user-friendly messages
- Network errors: caught by OkHttp, trigger offline mode
- Camera errors: caught by CameraX callbacks, displayed with retry option
- Location errors: timeout after 10s, allow capture without location (with warning)
- All errors logged locally with timestamp for debugging

## Security (Phase 1 Scope)

- JWT stored in EncryptedSharedPreferences (backed by Android Keystore)
- HTTPS for all API communication (HTTP allowed only for `10.0.2.2` in debug builds)
- No screenshots on login screen (`FLAG_SECURE`)
- Token cleared on logout

## Minimum Android Version Rationale

API 24 (Android 7.0) chosen because:
- CameraX requires API 21+
- Jetpack Compose requires API 21+
- EncryptedSharedPreferences requires API 23+
- FusedLocationProviderClient works on API 16+
- WorkManager works on API 14+
- API 24 gives ~97% device coverage and avoids API 23 edge cases with runtime permissions
