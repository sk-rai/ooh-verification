# Maestro E2E Test Flows — TrustCapture Vendor

End-to-end UI tests using [Maestro](https://maestro.mobile.dev/) for the TrustCapture Android app.

## Prerequisites

- Maestro CLI installed (`curl -Ls "https://get.maestro.mobile.dev" | bash`)
- Android emulator running or physical device connected via ADB
- App installed: `com.lynksavvy.trustcapture`
- For login tests: a valid test Vendor ID and phone number with OTP bypass

## Flow Summary

| # | File | Description |
|---|------|-------------|
| 01 | `01_login_flow.yaml` | Login with Vendor ID + Phone + OTP verification |
| 02 | `02_quick_capture_photo.yaml` | Quick Capture photo with text note and upload |
| 03 | `03_video_recording.yaml` | Video recording with mode switch and upload |
| 04 | `04_voice_note.yaml` | Photo capture with voice note attachment |
| 05 | `05_campaign_flow.yaml` | Campaign-based capture at assigned location |
| 06 | `06_settings_tracking.yaml` | Settings screen navigation and verification |
| 07 | `07_my_route.yaml` | My Route Today screen (tracking-dependent) |
| 08 | `08_full_regression.yaml` | Full regression — verifies all screens accessible |

## Running

### Run all flows:
```bash
maestro test .maestro/
```

### Run a single flow:
```bash
maestro test .maestro/01_login_flow.yaml
```

### Run with verbose output:
```bash
maestro test --debug-output .maestro/02_quick_capture_photo.yaml
```

## Architecture Notes

### Selector Strategy
- **Text-based selectors** are used throughout (not resource IDs) because the app uses Jetpack Compose, where `id` selectors don't reliably work with Maestro.
- **Coordinate taps** (`point: "50%,85%"`) are used for icon-only buttons (Settings gear, back arrow, camera shutter) that lack text labels.
- **Conditional flows** (`runFlow: when: visible:`) handle optional dialogs (permissions, privacy consent, background location).

### Timeouts
- **Camera/GPS**: 35s — GPS lock can take time on emulators
- **Network calls** (campaigns): 15s
- **Upload**: 5s — uses save-first architecture (instant local save + background sync)
- **OTP screen transition**: 10s

### Known Considerations
- `07_my_route.yaml` only executes if tracking is enabled (conditional flow)
- Permission dialogs vary by Android version and device state
- First launch may show Privacy Policy consent screen
- The `swipe` with `duration` is used as a wait/delay mechanism during recording

## Selector Reference (Actual UI Text)

### Login Screen
- Title: "TrustCapture"
- Subtitle: "Vendor Photo Capture"
- Fields: "Vendor ID", "Phone Number"
- Button: "Request OTP"

### OTP Screen
- Heading: "Enter Verification Code"
- Field: "6-digit OTP"
- Button: "Verify & Login"

### Home Screen
- Prompt: "What would you like to do?"
- Cards: "My Campaigns", "Quick Capture", "My Route Today"

### Camera Screen
- Mode labels: "PHOTO", "VIDEO"
- Recording indicator: "REC"

### Review Screen
- Titles: "Review Photo", "Review Video"
- Sections: "Capture Details"
- Note field: "Add observations"
- Buttons: "Retake", "Upload"
- Success: "uploaded successfully"

### Settings Screen
- Title: "Settings"
- Sections: "Location Tracking", "Account", "Device Security", "About"
