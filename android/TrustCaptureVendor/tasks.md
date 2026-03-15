# Android Vendor App — Phase 1 Implementation Tasks

## Phase 1: Core MVP (Auth → Camera → Upload)

- [x] 1. Development Environment Setup ✅ COMPLETE
  - [x] 1.1 Install Android Studio (latest stable) on Windows
  - [x] 1.2 Configure Android SDK (API 34 UpsideDownCake installed, API 36.1 Baklava also available)
  - [x] 1.3 Create and configure Android Emulator (Pixel 6, API 34, Google APIs Intel x86_64)
  - [x] 1.4 Verify emulator can reach WSL backend at `10.0.2.2:8000` via port forwarding
  - [x] 1.5 Swagger UI confirmed loading at `http://10.0.2.2:8000/api/docs` in emulator
  - Notes:
    - Android Studio installed at default Windows location
    - SDK location: `C:\Users\SANTOSH\AppData\Local\Android\Sdk`
    - WSL→Windows port forwarding configured (see `ANDROID_WSL_CONNECTIVITY.md`)
    - Project will be created at: `C:\Users\SANTOSH\Documents\Photo_verification\android`

- [x] 2. Project Scaffolding & Dependencies ✅ COMPLETE
  - [x] 2.1 Create new Android project at `C:\Users\SANTOSH\Documents\Photo_verification\android\TrustCaptureVendor`
  - [x] 2.2 Configure Gradle with all dependencies (Compose BOM, Material 3, Hilt, Retrofit, Room, CameraX, Coil, DataStore, Play Services Location)
  - [x] 2.3 Create package structure: `data/`, `domain/`, `ui/`, `di/`, `util/`
  - [x] 2.4 Set up Hilt application class and DI modules (NetworkModule, DatabaseModule, AppModule)
  - [x] 2.5 Configure Retrofit with OkHttp client (base URL `10.0.2.2:8000`, auth interceptor, tenant header interceptor)
  - [x] 2.6 Define API service interfaces: `AuthApi`, `CampaignApi`, `PhotoApi`
  - [x] 2.7 Set up Room database with initial entity stubs (CampaignEntity, PendingPhotoEntity)
  - [x] 2.8 Set up Compose Navigation (NavHost, routes for login/otp/campaigns/camera)
  - [x] 2.9 Create base theme (Material 3 dynamic color, TrustCapture branding)

- [ ] 3. Authentication Flow (OTP-based)
  - [ ] 3.1 Create data models: `OtpRequest`, `OtpVerifyRequest`, `AuthToken`, `VendorProfile`
  - [ ] 3.2 Implement `AuthRepository` — request OTP (`POST /api/auth/vendor/otp`), verify OTP (`POST /api/auth/vendor/verify`)
  - [ ] 3.3 Store JWT in DataStore, load on app start
  - [ ] 3.4 Build Login screen (phone input + request OTP button)
  - [ ] 3.5 Build OTP verification screen (6-digit input + verify button + resend timer)
  - [ ] 3.6 Implement `AuthViewModel` with login state management
  - [ ] 3.7 Add auth interceptor to OkHttp — attach `Authorization: Bearer <token>`
  - [ ] 3.8 Add tenant header interceptor — attach `X-Tenant-ID` header
  - [ ] 3.9 Handle token expiry (401 → redirect to login)
  - [ ] 3.10 Test auth flow end-to-end against WSL backend

- [ ] 4. Campaign List & Assignment View
  - [ ] 4.1 Create data models: `Campaign`, `Assignment`, `CampaignLocation`
  - [ ] 4.2 Implement `CampaignRepository` — fetch assigned campaigns
  - [ ] 4.3 Build Campaign List screen (pull-to-refresh, campaign cards)
  - [ ] 4.4 Build Campaign Detail screen (location list, assignment status)
  - [ ] 4.5 Implement `CampaignViewModel` with loading/error/empty states
  - [ ] 4.6 Test campaign list against WSL backend

- [ ] 5. Camera Capture (CameraX)
  - [ ] 5.1 Add CameraX dependencies and camera permission handling
  - [ ] 5.2 Build Camera Preview screen with Compose
  - [ ] 5.3 Implement photo capture with ImageCapture use case
  - [ ] 5.4 Save captured photo to app-internal storage
  - [ ] 5.5 Build Photo Review screen (preview + retake/accept)
  - [ ] 5.6 Embed EXIF metadata: timestamp, GPS coordinates
  - [ ] 5.7 Implement `CameraViewModel` with capture state management
  - [ ] 5.8 Test camera capture on emulator

- [ ] 6. Location Services
  - [ ] 6.1 Add location permission handling (FINE + COARSE)
  - [ ] 6.2 Implement `LocationService` using FusedLocationProviderClient
  - [ ] 6.3 Get current location at photo capture time
  - [ ] 6.4 Attach lat/lng to photo metadata before upload
  - [ ] 6.5 Handle location unavailable gracefully
  - [ ] 6.6 Test location on emulator with mock location

- [ ] 7. Photo Upload
  - [ ] 7.1 Create data models: `PhotoUpload`, `UploadResponse`, `UploadProgress`
  - [ ] 7.2 Implement `PhotoRepository` — multipart upload (`POST /api/photos/upload`)
  - [ ] 7.3 Build Upload Progress UI
  - [ ] 7.4 Handle upload failures with retry
  - [ ] 7.5 Implement `UploadViewModel`
  - [ ] 7.6 Test upload end-to-end against WSL backend

- [ ] 8. Connectivity Monitoring & Error Handling
  - [ ] 8.1 Implement `ConnectivityMonitor` using ConnectivityManager
  - [ ] 8.2 Show offline banner when network unavailable
  - [ ] 8.3 Disable upload button when offline
  - [ ] 8.4 Standardized error handling: network, API (4xx/5xx), timeout
  - [ ] 8.5 Reusable error UI components (snackbar, retry dialog, full-screen error)
  - [ ] 8.6 Parse backend error format `{"detail": "..."}`

- [ ] 9. Permissions Management
  - [ ] 9.1 Centralized permission manager (camera, location)
  - [ ] 9.2 Permission rationale dialogs
  - [ ] 9.3 Handle "Don't ask again" → direct to app settings
  - [ ] 9.4 Gate features behind permission checks

- [ ] 10. Integration Testing & Polish
  - [ ] 10.1 Full flow test: Login → Campaigns → Camera → Upload
  - [ ] 10.2 Test error scenarios: wrong OTP, expired token, no network, no GPS, upload failure
  - [ ] 10.3 UI polish: loading skeletons, transitions, empty states
  - [ ] 10.4 Code cleanup: KDoc comments, no hardcoded strings
