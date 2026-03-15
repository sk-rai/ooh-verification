# Requirements Document: Android Vendor Application

## Introduction

The Android Vendor Application is a mobile app for field workers (vendors) to capture and upload photos of advertising campaigns with location verification and cryptographic signatures. The app integrates with the existing TrustCapture backend API to provide offline-first photo capture, automatic sync, and secure authentication for out-of-home (OOH) advertising verification.

This application supports multi-tenant white-label architecture, allowing different brands to deploy customized versions of the app with their own branding, while sharing the same codebase and backend infrastructure.

## Glossary

- **Vendor**: A field worker who captures photos of advertising campaigns using the Android app
- **Campaign**: A verification project with specific locations where photos must be captured
- **Photo_Capture**: The process of taking a photo with camera, GPS, and sensor data
- **Cryptographic_Signature**: A digital signature generated using Android Keystore to prove photo authenticity
- **Location_Verification**: The process of validating that a photo was captured at the expected GPS coordinates
- **Offline_Queue**: Local storage for photos captured without internet connectivity
- **Sync_Service**: Background service that uploads queued photos when connectivity is restored
- **OTP_Authentication**: One-time password sent via SMS for vendor login
- **Device_Registration**: The process of associating a vendor account with a specific Android device
- **SafetyNet_Attestation**: Google's API for verifying device integrity (not rooted/tampered)
- **White_Label_Config**: Tenant-specific branding configuration (logo, colors, app name)
- **Backend_API**: The existing TrustCapture REST API that handles authentication, campaigns, and photo uploads
- **Android_Keystore**: Hardware-backed secure storage for cryptographic keys on Android devices
- **Campaign_Assignment**: The association between a vendor and specific campaigns they can photograph
- **Geofence**: A virtual boundary around expected photo capture locations
- **EXIF_Data**: Metadata embedded in photo files including GPS coordinates and timestamps
- **JWT_Token**: JSON Web Token used for authenticating API requests
- **Background_Sync**: Automatic upload of queued photos when app is not in foreground

## Requirements

### Requirement 1: Vendor Authentication

**User Story:** As a vendor, I want to log in using my phone number and OTP, so that I can securely access the app without remembering passwords.

#### Acceptance Criteria

1. WHEN a vendor enters their phone number and vendor ID, THE Authentication_Module SHALL send an OTP request to the Backend_API
2. WHEN the Backend_API confirms OTP sent, THE Authentication_Module SHALL display an OTP input screen
3. WHEN a vendor enters a valid OTP, THE Authentication_Module SHALL verify the OTP with the Backend_API and receive a JWT_Token
4. WHEN authentication succeeds, THE Authentication_Module SHALL store the JWT_Token securely in Android Keystore
5. WHEN a vendor's JWT_Token expires, THE Authentication_Module SHALL prompt for re-authentication
6. IF the Backend_API returns an authentication error, THEN THE Authentication_Module SHALL display a descriptive error message
7. THE Authentication_Module SHALL validate phone number format before sending OTP request (E.164 format)
8. THE Authentication_Module SHALL validate vendor ID format (6 alphanumeric characters) before sending OTP request

### Requirement 2: Device Registration

**User Story:** As a vendor, I want my device to be registered on first login, so that my photos can be cryptographically verified.

#### Acceptance Criteria

1. WHEN a vendor logs in for the first time, THE Device_Registration_Module SHALL generate an RSA key pair in Android_Keystore
2. WHEN the key pair is generated, THE Device_Registration_Module SHALL extract the public key
3. WHEN the public key is extracted, THE Device_Registration_Module SHALL send the device ID and public key to the Backend_API
4. WHEN the Backend_API confirms registration, THE Device_Registration_Module SHALL mark the device as registered
5. THE Device_Registration_Module SHALL use hardware-backed Android_Keystore when available
6. IF Android_Keystore is not available, THEN THE Device_Registration_Module SHALL display an error and prevent app usage
7. THE Device_Registration_Module SHALL generate a unique device ID using Android's secure identifier APIs

### Requirement 3: Campaign List Display

**User Story:** As a vendor, I want to see my assigned campaigns, so that I know which locations to photograph.

#### Acceptance Criteria

1. WHEN the app launches after authentication, THE Campaign_Module SHALL fetch assigned campaigns from the Backend_API
2. WHEN campaigns are fetched, THE Campaign_Module SHALL display campaign name, code, type, and status
3. WHEN campaigns are fetched, THE Campaign_Module SHALL cache campaign data locally for offline access
4. WHEN a vendor taps a campaign, THE Campaign_Module SHALL display campaign details including locations
5. THE Campaign_Module SHALL display campaign start and end dates
6. THE Campaign_Module SHALL filter out expired campaigns from the active list
7. WHILE offline, THE Campaign_Module SHALL display cached campaign data
8. WHEN connectivity is restored, THE Campaign_Module SHALL refresh campaign data in the background

### Requirement 4: Camera Photo Capture

**User Story:** As a vendor, I want to capture photos with the camera, so that I can document advertising campaigns.

#### Acceptance Criteria

1. WHEN a vendor selects a campaign and taps "Capture Photo", THE Camera_Module SHALL request camera permission if not granted
2. WHEN camera permission is granted, THE Camera_Module SHALL open the device camera
3. WHEN a vendor captures a photo, THE Camera_Module SHALL save the photo to local storage
4. WHEN a photo is saved, THE Camera_Module SHALL extract EXIF_Data including GPS coordinates and timestamp
5. THE Camera_Module SHALL compress photos to maximum 5MB file size while maintaining quality
6. THE Camera_Module SHALL support both front and rear cameras
7. IF camera permission is denied, THEN THE Camera_Module SHALL display an explanation and link to settings
8. THE Camera_Module SHALL capture photos in JPEG format

### Requirement 5: Location Data Capture

**User Story:** As a vendor, I want GPS coordinates captured automatically with each photo, so that location can be verified.

#### Acceptance Criteria

1. WHEN the app launches, THE Location_Module SHALL request location permission if not granted
2. WHEN a photo is captured, THE Location_Module SHALL capture current GPS coordinates (latitude, longitude)
3. WHEN GPS coordinates are captured, THE Location_Module SHALL capture location accuracy in meters
4. WHEN GPS coordinates are captured, THE Location_Module SHALL capture altitude if available
5. THE Location_Module SHALL use high-accuracy location provider (GPS + Network)
6. IF location accuracy is worse than 50 meters, THEN THE Location_Module SHALL display a warning to the vendor
7. IF location permission is denied, THEN THE Location_Module SHALL prevent photo capture and display an error
8. THE Location_Module SHALL capture location timestamp synchronized with photo capture timestamp

### Requirement 6: Sensor Data Collection

**User Story:** As a vendor, I want device sensor data captured with each photo, so that photo authenticity can be verified.

#### Acceptance Criteria

1. WHEN a photo is captured, THE Sensor_Module SHALL capture accelerometer data (x, y, z axes)
2. WHEN a photo is captured, THE Sensor_Module SHALL capture gyroscope data (x, y, z axes)
3. WHEN a photo is captured, THE Sensor_Module SHALL capture magnetometer data (x, y, z axes)
4. WHEN a photo is captured, THE Sensor_Module SHALL capture device orientation (azimuth, pitch, roll)
5. WHEN a photo is captured, THE Sensor_Module SHALL capture ambient light level if sensor available
6. THE Sensor_Module SHALL capture sensor data within 1 second of photo capture
7. IF a sensor is not available, THEN THE Sensor_Module SHALL record null for that sensor's data
8. THE Sensor_Module SHALL bundle all sensor data into a JSON structure

### Requirement 7: Cryptographic Signature Generation

**User Story:** As a vendor, I want photos digitally signed with my device key, so that photo tampering can be detected.

#### Acceptance Criteria

1. WHEN a photo is captured, THE Signature_Module SHALL create a signature payload containing photo hash, GPS coordinates, timestamp, and sensor data
2. WHEN the signature payload is created, THE Signature_Module SHALL compute SHA-256 hash of the photo file
3. WHEN the photo hash is computed, THE Signature_Module SHALL sign the payload using the private key from Android_Keystore
4. WHEN the signature is generated, THE Signature_Module SHALL use RSA-SHA256 signing algorithm
5. THE Signature_Module SHALL include the signature in the photo upload metadata
6. THE Signature_Module SHALL never expose the private key outside Android_Keystore
7. FOR ALL captured photos, computing the signature then verifying with the public key SHALL return true (round-trip property)
8. IF signature generation fails, THEN THE Signature_Module SHALL prevent photo upload and log the error

### Requirement 8: Offline Photo Queue

**User Story:** As a vendor, I want photos saved locally when offline, so that I can continue working without internet connectivity.

#### Acceptance Criteria

1. WHEN a photo is captured, THE Offline_Queue SHALL save the photo and metadata to local storage
2. WHEN a photo is saved locally, THE Offline_Queue SHALL mark it as "pending upload"
3. WHEN connectivity is unavailable, THE Offline_Queue SHALL queue all captured photos
4. THE Offline_Queue SHALL store photos in encrypted local storage
5. THE Offline_Queue SHALL persist queue state across app restarts
6. THE Offline_Queue SHALL display the number of pending uploads to the vendor
7. WHEN storage space is low, THE Offline_Queue SHALL display a warning to the vendor
8. THE Offline_Queue SHALL limit queue size to 100 photos maximum

### Requirement 9: Background Sync Service

**User Story:** As a vendor, I want photos automatically uploaded when internet is available, so that I don't have to manually sync.

#### Acceptance Criteria

1. WHEN connectivity is restored, THE Sync_Service SHALL automatically start uploading queued photos
2. WHEN uploading photos, THE Sync_Service SHALL upload photos in FIFO order (oldest first)
3. WHEN a photo upload succeeds, THE Sync_Service SHALL remove the photo from the Offline_Queue
4. WHEN a photo upload succeeds, THE Sync_Service SHALL delete the local photo file
5. IF a photo upload fails, THEN THE Sync_Service SHALL retry with exponential backoff (max 3 retries)
6. IF a photo upload fails after 3 retries, THEN THE Sync_Service SHALL mark it as "failed" and notify the vendor
7. THE Sync_Service SHALL run in the background even when the app is not in foreground
8. THE Sync_Service SHALL respect Android battery optimization settings
9. WHILE uploading, THE Sync_Service SHALL display upload progress to the vendor
10. THE Sync_Service SHALL use WorkManager for reliable background execution

### Requirement 10: Photo Upload to Backend

**User Story:** As a vendor, I want photos uploaded to the backend API, so that clients can view and verify them.

#### Acceptance Criteria

1. WHEN uploading a photo, THE Upload_Module SHALL send a multipart HTTP POST request to the Backend_API
2. WHEN uploading a photo, THE Upload_Module SHALL include the photo file, campaign code, GPS coordinates, timestamp, sensor data, and cryptographic signature
3. WHEN uploading a photo, THE Upload_Module SHALL include the JWT_Token in the Authorization header
4. WHEN the Backend_API returns success, THE Upload_Module SHALL mark the photo as uploaded
5. IF the Backend_API returns 401 Unauthorized, THEN THE Upload_Module SHALL trigger re-authentication
6. IF the Backend_API returns 413 Payload Too Large, THEN THE Upload_Module SHALL display an error about file size
7. IF the Backend_API returns 422 Unprocessable Entity, THEN THE Upload_Module SHALL display validation errors
8. THE Upload_Module SHALL timeout requests after 60 seconds
9. THE Upload_Module SHALL compress photos before upload to reduce bandwidth usage

### Requirement 11: Campaign Location Display

**User Story:** As a vendor, I want to see campaign locations on a map, so that I can navigate to photo capture sites.

#### Acceptance Criteria

1. WHEN a vendor views campaign details, THE Map_Module SHALL display campaign locations on a Google Map
2. WHEN locations are displayed, THE Map_Module SHALL show markers for each expected location
3. WHEN locations are displayed, THE Map_Module SHALL show the vendor's current location
4. WHEN a vendor taps a location marker, THE Map_Module SHALL display location details (address, coordinates)
5. THE Map_Module SHALL calculate and display distance from current location to each campaign location
6. THE Map_Module SHALL provide a "Navigate" button that opens Google Maps for turn-by-turn directions
7. WHILE offline, THE Map_Module SHALL display cached map tiles if available
8. THE Map_Module SHALL highlight locations where photos have already been captured

### Requirement 12: Device Integrity Verification

**User Story:** As a system administrator, I want to detect rooted or tampered devices, so that photo authenticity is ensured.

#### Acceptance Criteria

1. WHEN the app launches, THE Integrity_Module SHALL perform SafetyNet_Attestation check
2. WHEN SafetyNet_Attestation completes, THE Integrity_Module SHALL verify the device passes basic integrity
3. IF the device fails basic integrity, THEN THE Integrity_Module SHALL display a warning to the vendor
4. IF the device fails CTS profile match, THEN THE Integrity_Module SHALL log the failure but allow app usage
5. THE Integrity_Module SHALL perform integrity checks every 24 hours
6. THE Integrity_Module SHALL send integrity check results to the Backend_API with each photo upload
7. IF SafetyNet_Attestation API is unavailable, THEN THE Integrity_Module SHALL log the error and continue
8. THE Integrity_Module SHALL detect root access using multiple detection methods (su binary, root management apps, build tags)

### Requirement 13: White-Label Branding

**User Story:** As a tenant administrator, I want the app to display my brand colors and logo, so that vendors see a customized experience.

#### Acceptance Criteria

1. WHEN the app launches, THE Branding_Module SHALL fetch tenant configuration from the Backend_API
2. WHEN tenant configuration is fetched, THE Branding_Module SHALL apply primary and secondary colors to the UI
3. WHEN tenant configuration is fetched, THE Branding_Module SHALL display the tenant logo in the app header
4. WHEN tenant configuration is fetched, THE Branding_Module SHALL cache branding data locally
5. THE Branding_Module SHALL apply branding to splash screen, login screen, and main navigation
6. WHERE a tenant has a custom app name, THE Branding_Module SHALL display the custom name in the app title
7. THE Branding_Module SHALL support dynamic theme switching without app restart
8. WHILE offline, THE Branding_Module SHALL use cached branding configuration

### Requirement 14: Photo Capture History

**User Story:** As a vendor, I want to view my photo capture history, so that I can track my work progress.

#### Acceptance Criteria

1. WHEN a vendor navigates to the history screen, THE History_Module SHALL display a list of captured photos
2. WHEN displaying photo history, THE History_Module SHALL show photo thumbnail, campaign name, capture timestamp, and upload status
3. WHEN a vendor taps a photo in history, THE History_Module SHALL display full photo details including location and verification status
4. THE History_Module SHALL filter photos by campaign
5. THE History_Module SHALL filter photos by date range
6. THE History_Module SHALL sort photos by capture timestamp (newest first)
7. THE History_Module SHALL display upload status indicators (pending, uploading, uploaded, failed)
8. THE History_Module SHALL paginate results to display 20 photos per page

### Requirement 15: Network Connectivity Monitoring

**User Story:** As a vendor, I want to see my connectivity status, so that I know when photos will sync.

#### Acceptance Criteria

1. WHEN network connectivity changes, THE Connectivity_Module SHALL detect the change
2. WHEN connectivity is lost, THE Connectivity_Module SHALL display an offline indicator in the UI
3. WHEN connectivity is restored, THE Connectivity_Module SHALL display an online indicator and trigger sync
4. THE Connectivity_Module SHALL distinguish between WiFi and cellular connectivity
5. WHERE the vendor has disabled cellular uploads in settings, THE Connectivity_Module SHALL only sync on WiFi
6. THE Connectivity_Module SHALL monitor connectivity continuously while the app is running
7. THE Connectivity_Module SHALL register a broadcast receiver for connectivity changes when app is in background
8. THE Connectivity_Module SHALL display estimated data usage for pending uploads

### Requirement 16: Error Handling and Logging

**User Story:** As a developer, I want comprehensive error logging, so that I can troubleshoot issues reported by vendors.

#### Acceptance Criteria

1. WHEN an error occurs, THE Error_Handler SHALL log the error with timestamp, error type, and stack trace
2. WHEN an error occurs, THE Error_Handler SHALL display a user-friendly error message to the vendor
3. WHEN a critical error occurs, THE Error_Handler SHALL send an error report to the Backend_API
4. THE Error_Handler SHALL log API request failures including status code and response body
5. THE Error_Handler SHALL log photo capture failures including camera errors and permission denials
6. THE Error_Handler SHALL log location errors including GPS unavailability and accuracy issues
7. THE Error_Handler SHALL store logs locally for 7 days
8. WHERE the vendor enables crash reporting in settings, THE Error_Handler SHALL send crash reports to Firebase Crashlytics

### Requirement 17: Settings and Preferences

**User Story:** As a vendor, I want to configure app settings, so that I can customize my experience.

#### Acceptance Criteria

1. WHEN a vendor navigates to settings, THE Settings_Module SHALL display configurable preferences
2. THE Settings_Module SHALL allow enabling/disabling cellular data uploads (WiFi-only mode)
3. THE Settings_Module SHALL allow enabling/disabling crash reporting
4. THE Settings_Module SHALL allow enabling/disabling location services (with warning)
5. THE Settings_Module SHALL display app version and build number
6. THE Settings_Module SHALL provide a "Clear Cache" option to delete cached data
7. THE Settings_Module SHALL provide a "Logout" option to clear authentication and return to login screen
8. THE Settings_Module SHALL persist preferences across app restarts

### Requirement 18: Photo Compression and Optimization

**User Story:** As a vendor, I want photos automatically optimized, so that uploads are faster and use less data.

#### Acceptance Criteria

1. WHEN a photo is captured, THE Compression_Module SHALL compress the photo to maximum 5MB file size
2. WHEN compressing photos, THE Compression_Module SHALL maintain JPEG quality of at least 85%
3. WHEN compressing photos, THE Compression_Module SHALL preserve EXIF_Data including GPS coordinates
4. THE Compression_Module SHALL resize photos to maximum 4000x3000 pixels
5. THE Compression_Module SHALL generate a thumbnail at 400x300 pixels for local preview
6. IF a photo is already under 5MB, THEN THE Compression_Module SHALL not re-compress it
7. THE Compression_Module SHALL perform compression on a background thread to avoid UI blocking
8. THE Compression_Module SHALL display compression progress for large photos

### Requirement 19: Permission Management

**User Story:** As a vendor, I want clear permission requests, so that I understand why the app needs access to device features.

#### Acceptance Criteria

1. WHEN the app first requests camera permission, THE Permission_Module SHALL display an explanation dialog
2. WHEN the app first requests location permission, THE Permission_Module SHALL display an explanation dialog
3. WHEN the app first requests storage permission, THE Permission_Module SHALL display an explanation dialog
4. IF a vendor denies a required permission, THEN THE Permission_Module SHALL display the impact and link to settings
5. THE Permission_Module SHALL request permissions at the point of use, not on app launch
6. THE Permission_Module SHALL handle Android 11+ scoped storage requirements
7. THE Permission_Module SHALL request background location permission separately from foreground permission
8. THE Permission_Module SHALL comply with Google Play permission policy requirements

### Requirement 20: Geofence Validation

**User Story:** As a vendor, I want to be notified if I'm too far from expected locations, so that I can capture photos at the correct sites.

#### Acceptance Criteria

1. WHEN a vendor captures a photo, THE Geofence_Module SHALL calculate distance from expected campaign locations
2. IF the distance is greater than 500 meters from any expected location, THEN THE Geofence_Module SHALL display a warning
3. WHEN displaying a geofence warning, THE Geofence_Module SHALL show the distance to the nearest expected location
4. THE Geofence_Module SHALL allow the vendor to proceed with photo capture despite the warning
5. THE Geofence_Module SHALL include geofence validation results in photo metadata
6. WHERE a campaign has no specific locations defined, THE Geofence_Module SHALL skip validation
7. THE Geofence_Module SHALL use Haversine formula for distance calculation
8. THE Geofence_Module SHALL display expected location address in the warning message

### Requirement 21: Battery Optimization

**User Story:** As a vendor, I want the app to minimize battery drain, so that I can work all day without recharging.

#### Acceptance Criteria

1. WHEN the app is in background, THE Battery_Module SHALL reduce GPS polling frequency to every 5 minutes
2. WHEN the app is in foreground, THE Battery_Module SHALL use high-accuracy GPS polling
3. THE Battery_Module SHALL stop GPS polling when no active photo capture is in progress
4. THE Battery_Module SHALL use WorkManager for background sync to respect Doze mode
5. THE Battery_Module SHALL batch API requests when possible to reduce radio wake-ups
6. THE Battery_Module SHALL release camera resources immediately after photo capture
7. THE Battery_Module SHALL use efficient image loading libraries (Glide/Coil) for thumbnails
8. WHERE battery level is below 15%, THE Battery_Module SHALL display a low battery warning and suggest disabling background sync

### Requirement 22: Multi-Language Support

**User Story:** As a vendor, I want the app in my preferred language, so that I can use it comfortably.

#### Acceptance Criteria

1. WHEN the app launches, THE Localization_Module SHALL detect the device language setting
2. WHERE the device language is supported, THE Localization_Module SHALL display the UI in that language
3. WHERE the device language is not supported, THE Localization_Module SHALL default to English
4. THE Localization_Module SHALL support English, Hindi, Spanish, and French at minimum
5. THE Localization_Module SHALL localize all UI text, error messages, and notifications
6. THE Localization_Module SHALL format dates and times according to device locale
7. THE Localization_Module SHALL format numbers and currencies according to device locale
8. THE Localization_Module SHALL allow manual language selection in settings

### Requirement 23: Notification System

**User Story:** As a vendor, I want notifications about upload status, so that I know when photos are successfully synced.

#### Acceptance Criteria

1. WHEN a photo upload completes successfully, THE Notification_Module SHALL display a success notification
2. WHEN all queued photos are uploaded, THE Notification_Module SHALL display a completion notification
3. IF a photo upload fails after retries, THEN THE Notification_Module SHALL display a failure notification
4. WHEN a new campaign is assigned, THE Notification_Module SHALL display a notification
5. THE Notification_Module SHALL group multiple upload notifications into a summary notification
6. THE Notification_Module SHALL allow vendors to disable notifications in settings
7. THE Notification_Module SHALL use notification channels for Android 8.0+ compatibility
8. THE Notification_Module SHALL display upload progress in the notification for large files

### Requirement 24: Security and Data Protection

**User Story:** As a security administrator, I want sensitive data encrypted, so that vendor information is protected.

#### Acceptance Criteria

1. WHEN storing JWT_Token, THE Security_Module SHALL encrypt it using Android_Keystore
2. WHEN storing photos in Offline_Queue, THE Security_Module SHALL encrypt files using AES-256
3. WHEN communicating with Backend_API, THE Security_Module SHALL use HTTPS with TLS 1.2 or higher
4. THE Security_Module SHALL implement certificate pinning for Backend_API connections
5. THE Security_Module SHALL clear sensitive data from memory after use
6. THE Security_Module SHALL prevent screenshots in authentication screens
7. THE Security_Module SHALL implement ProGuard/R8 code obfuscation for release builds
8. THE Security_Module SHALL validate all API responses to prevent injection attacks

### Requirement 25: App Update Management

**User Story:** As a vendor, I want to be notified of app updates, so that I can use the latest features and fixes.

#### Acceptance Criteria

1. WHEN the app launches, THE Update_Module SHALL check for available updates from Google Play
2. IF a critical update is available, THEN THE Update_Module SHALL display a mandatory update dialog
3. IF a non-critical update is available, THEN THE Update_Module SHALL display an optional update notification
4. WHEN a vendor accepts an update, THE Update_Module SHALL redirect to Google Play Store
5. THE Update_Module SHALL check for updates once per day maximum
6. THE Update_Module SHALL use Google Play In-App Updates API for seamless updates
7. WHERE an immediate update is required, THE Update_Module SHALL prevent app usage until updated
8. THE Update_Module SHALL display update release notes in the update dialog

### Requirement 26: Accessibility Support

**User Story:** As a vendor with visual impairments, I want the app to support accessibility features, so that I can use it effectively.

#### Acceptance Criteria

1. THE Accessibility_Module SHALL support TalkBack screen reader for all UI elements
2. THE Accessibility_Module SHALL provide content descriptions for all images and icons
3. THE Accessibility_Module SHALL ensure minimum touch target size of 48dp for all interactive elements
4. THE Accessibility_Module SHALL provide sufficient color contrast (WCAG AA minimum)
5. THE Accessibility_Module SHALL support dynamic text sizing based on system font size
6. THE Accessibility_Module SHALL provide haptic feedback for important actions
7. THE Accessibility_Module SHALL ensure all functionality is accessible without color perception
8. THE Accessibility_Module SHALL support keyboard navigation where applicable

### Requirement 27: Performance Monitoring

**User Story:** As a product manager, I want to monitor app performance metrics, so that I can identify and fix performance issues.

#### Acceptance Criteria

1. WHEN the app launches, THE Performance_Module SHALL measure and log app startup time
2. WHEN a photo is captured, THE Performance_Module SHALL measure and log capture-to-save duration
3. WHEN a photo is uploaded, THE Performance_Module SHALL measure and log upload duration
4. THE Performance_Module SHALL monitor memory usage and log warnings when exceeding thresholds
5. THE Performance_Module SHALL monitor frame rate and log warnings when dropping below 30 FPS
6. THE Performance_Module SHALL send performance metrics to Firebase Performance Monitoring
7. THE Performance_Module SHALL track API response times for all Backend_API calls
8. THE Performance_Module SHALL track crash-free user rate and ANR (Application Not Responding) rate

### Requirement 28: Vendor Profile Management

**User Story:** As a vendor, I want to view and update my profile information, so that my contact details are current.

#### Acceptance Criteria

1. WHEN a vendor navigates to profile screen, THE Profile_Module SHALL display vendor name, phone number, email, and vendor ID
2. WHEN a vendor navigates to profile screen, THE Profile_Module SHALL display device registration status
3. THE Profile_Module SHALL display the number of campaigns assigned to the vendor
4. THE Profile_Module SHALL display the total number of photos captured by the vendor
5. THE Profile_Module SHALL allow vendors to update their email address
6. WHEN a vendor updates email, THE Profile_Module SHALL send the update to the Backend_API
7. THE Profile_Module SHALL display last login timestamp
8. THE Profile_Module SHALL display app version and device information for support purposes

### Requirement 29: Campaign Search and Filter

**User Story:** As a vendor, I want to search and filter campaigns, so that I can quickly find specific assignments.

#### Acceptance Criteria

1. WHEN a vendor enters text in the search box, THE Search_Module SHALL filter campaigns by name or code
2. THE Search_Module SHALL support filtering campaigns by status (active, completed, cancelled)
3. THE Search_Module SHALL support filtering campaigns by campaign type
4. THE Search_Module SHALL support sorting campaigns by start date, end date, or name
5. THE Search_Module SHALL display search results in real-time as the vendor types
6. THE Search_Module SHALL highlight matching text in search results
7. WHEN no campaigns match the search criteria, THE Search_Module SHALL display a "no results" message
8. THE Search_Module SHALL persist search and filter preferences across app sessions

### Requirement 30: Retry Failed Uploads

**User Story:** As a vendor, I want to manually retry failed uploads, so that I can ensure all photos are submitted.

#### Acceptance Criteria

1. WHEN a vendor views failed uploads, THE Retry_Module SHALL display a list of photos that failed to upload
2. WHEN a vendor taps a failed photo, THE Retry_Module SHALL display the failure reason
3. WHEN a vendor taps "Retry", THE Retry_Module SHALL attempt to upload the photo again
4. WHEN a vendor taps "Retry All", THE Retry_Module SHALL attempt to upload all failed photos
5. THE Retry_Module SHALL allow vendors to delete failed photos from the queue
6. THE Retry_Module SHALL display the number of retry attempts for each failed photo
7. IF a photo fails due to validation errors, THEN THE Retry_Module SHALL display the specific validation errors
8. THE Retry_Module SHALL move successfully retried photos to the uploaded list
