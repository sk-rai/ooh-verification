# Play Store Listing Content

## App Name
TrustCapture - Photo Verification

## Short Description (80 chars max)
Tamper-proof photo verification with GPS, sensors & cryptographic signatures.

## Full Description (4000 chars max)

TrustCapture is a field photo verification app for vendors and field workers. Every photo is GPS-stamped, sensor-validated, and cryptographically signed using your device's hardware security module — making it impossible to fake location, timestamp, or image authenticity.

BUILT FOR FIELD OPERATIONS
Whether you're verifying billboard installations, documenting deliveries, or conducting site inspections, TrustCapture ensures every photo is captured live, at the right place, at the right time.

HOW IT WORKS
1. Log in with your Vendor ID and OTP (first time only — subsequent logins use device key authentication, no SMS needed)
2. Select your assigned campaign
3. Capture photos — GPS, barometric pressure, magnetic field, and accelerometer data are collected automatically
4. Photos are signed with your device's hardware-backed key and uploaded securely

KEY FEATURES
• Forced live capture — gallery uploads blocked, every photo must be taken through the camera
• GPS geofence verification — photos captured outside the designated area are flagged
• Multi-sensor validation — barometric pressure, magnetic field, and hand tremor analysis
• Hardware-backed signatures — ECDSA keys stored in Android StrongBox/TEE, impossible to clone
• Visible watermarks — GPS coordinates, timestamp, and vendor ID burned into image pixels
• Offline-ready — photos stored in encrypted local database, auto-uploaded when connectivity returns
• Background sync — WorkManager handles uploads even when the app is closed
• Device key authentication — after first OTP login, sign in instantly with hardware key (no SMS costs)
• Battery optimized — adaptive GPS power modes reduce battery drain during extended field sessions

SECURITY
• End-to-end encryption for photo storage and transmission
• SQLCipher encrypted local database
• Certificate pinning for API communication
• No photo data stored on device after successful upload
• GDPR-compliant with privacy consent and data export options

REQUIREMENTS
• Android 7.0 (API 24) or higher
• Camera and GPS access required
• Internet connection for upload (offline capture supported)
• Vendor ID provided by your employer

TrustCapture is part of the TrustCapture platform by LynkSavvy Technologies. Clients manage campaigns, vendors, and verification results through the web dashboard at trustcapture.com.

## Category
Business

## Content Rating
Suitable for all ages (business tool, no user-generated content visible to others)

## Contact Details
- Email: support@lynksavvy.com
- Website: https://trustcapture.com

## Data Safety Declaration Answers

### Data collected:
| Data Type | Collected | Shared | Purpose |
|-----------|-----------|--------|---------|
| Precise location (GPS) | Yes | Yes (sent to server) | App functionality — geofence verification |
| Photos | Yes | Yes (uploaded to server) | App functionality — photo verification |
| Device ID (Android ID) | Yes | Yes (sent to server) | App functionality — device authentication |
| Phone number | Yes | Yes (sent to server) | Account management — OTP login |
| Barometric pressure | Yes | Yes (sent to server) | App functionality — altitude verification |
| Magnetic field data | Yes | Yes (sent to server) | App functionality — location validation |
| Accelerometer data | Yes | Yes (sent to server) | App functionality — tremor analysis |
| WiFi scan results | Yes | Yes (sent to server) | App functionality — location triangulation |
| Cell tower info | Yes | Yes (sent to server) | App functionality — location triangulation |

### Data handling:
- Data is encrypted in transit (HTTPS/TLS)
- Data is encrypted at rest (SQLCipher on device, encrypted storage on server)
- Users can request data deletion (GDPR Article 17)
- Data is not sold to third parties

### Security practices:
- Data encrypted in transit: Yes
- Data can be deleted by user request: Yes
- Independent security review: No (not yet)
