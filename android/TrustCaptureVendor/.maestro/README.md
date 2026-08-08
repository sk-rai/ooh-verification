# Maestro UI Tests for TrustCapture

## Setup

Install Maestro (macOS/Linux):
```bash
curl -Ls "https://get.maestro.mobile.dev" | bash
```

For Windows, use WSL or run via Android emulator on WSL.

## Running Tests

Run all flows:
```bash
maestro test .maestro/
```

Run a single flow:
```bash
maestro test .maestro/01_login_flow.yaml
```

## Prerequisites

- Android emulator running OR device connected via USB with ADB
- App installed (debug APK)
- For login flow: backend test mode accepts OTP "123456" for test numbers
- For GPS-dependent tests: emulator should have a mock location set

## Flow Descriptions

| Flow | What it tests |
|------|--------------|
| 01_login_flow | Phone + OTP login → Home screen |
| 02_quick_capture_photo | Quick Capture → photo → text note → upload |
| 03_video_recording | Quick Capture → video mode → record → stop → review → upload |
| 04_voice_note | Quick Capture → photo → voice note → stop → upload |
| 05_campaign_flow | Campaigns list → location → photo → upload |

## Notes

- Flows use coordinate-based taps for camera buttons (center of screen)
- The `extendedWaitUntil` with 35s timeout accounts for GPS acquisition time
- Upload timeouts are set to 70-130s to account for network variability
- Voice note and video tests need a real device for best results (emulator may have issues with MediaRecorder)
- These are smoke tests — they verify the happy path UI flows work end-to-end
