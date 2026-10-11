# TrustCapture Android Demo — Shot List & Capture Guide

## Target Canvas
**Portrait, 1080×2340** (or whatever the emulator captures natively — all frames fit+padded to one canvas).
Decision: **Portrait** (natural for a phone field app). Do NOT mix landscape.

## Capture Settings

Use ADB to capture clean screenshots (no status bar clutter, native resolution):

```powershell
# From Windows PowerShell, with emulator or phone connected:
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" exec-out screencap -p > android-demo-shots\NN-name.png
```

Replace `NN-name` with the exact filenames below. Capture in order.

**Tip:** Enable "Show taps" in Developer Options is NOT needed. For cleanest shots, you can hide the clock/notifications via demo mode:
```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell settings put global sysui_demo_allowed 1
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell am broadcast -a com.android.systemui.demo -e command enter
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell am broadcast -a com.android.systemui.demo -e command clock -e hhmm 0900
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell am broadcast -a com.android.systemui.demo -e command battery -e level 100 -e plugged false
# ... capture shots ...
# Exit demo mode after:
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell am broadcast -a com.android.systemui.demo -e command exit
```

## Shot List (ordered)

| # | Filename | Screen | Caption | Draft Narration |
|---|----------|--------|---------|-----------------|
| 01 | `01-privacy.png` | Privacy & Data Collection consent | "Transparent consent before any data is collected" | "Every TrustCapture session begins with clear, GDPR-aligned consent — the vendor sees exactly what's collected and why." |
| 02 | `02-login.png` | Login (Vendor ID + Phone) | "Secure vendor sign-in" | "Field vendors sign in with their assigned ID and phone number — no passwords to manage or leak." |
| 03 | `03-otp.png` | OTP verification | "One-time passcode verification" | "A one-time passcode confirms identity, and the device is bound to a hardware-backed signing key for tamper-proof evidence." |
| 04 | `04-home.png` | Home screen | "A clear starting point for field work" | "The home screen offers two paths — capture against an assigned campaign, or quick-capture for spontaneous evidence." |
| 05 | `05-campaigns.png` | My Campaigns list | "Assigned campaigns, synced from the backend" | "Vendors see only the campaigns assigned to them, each with its own capture rules and locations." |
| 06 | `06-locations.png` | Locations list | "Each campaign's verified locations" | "Within a campaign, every location carries its expected coordinates for on-site verification." |
| 07 | `07-camera-photo.png` | Camera — photo mode (GPS + sensors visible) | "Live GPS, compass, and sensor capture" | "At the point of capture, TrustCapture records GPS, compass heading, WiFi, cell towers, and environmental sensors — a multi-signal fingerprint of the moment." |
| 08 | `08-camera-video.png` | Camera — video mode | "Video evidence with a GPS track" | "Switch to video for continuous proof, with a GPS track recorded second-by-second throughout." |
| 09 | `09-review.png` | Review screen (watermark + metadata) | "Every capture is watermarked and signed" | "Each capture is watermarked with location and time, then signed with the device key — any later edit breaks the signature." |
| 10 | `10-voice-note.png` | Review — voice note recorded | "Attach voice and text notes" | "Vendors can attach a voice note or written observations, giving context the photo alone can't convey." |
| 11 | `11-upload-success.png` | Upload success | "Instant save, background upload" | "Evidence saves instantly on-device and uploads in the background — vendors never wait on a slow network." |
| 12 | `12-settings.png` | Settings — Location Tracking | "Backend-configurable behavior" | "Nearly every behavior — capture limits, tracking, branding — is controlled from the backend, so policy changes need no app update." |
| 13 | `13-my-route.png` | My Route Today | "A verifiable record of the day" | "And at day's end, My Route shows a verifiable trail of where the vendor worked — distance, duration, and every tracked point." |

## Closing Card
Consistent with web demo:
**"TrustCapture — trusted evidence for field operations"**

## Notes for Capture
- For shot 07/08: wait for GPS to lock (status chip shows "GPS Ready" or "GPS OK") so the sensor chips are populated.
- For shot 09: capture a real photo so the watermark is visible.
- For shot 10: record a short voice note first so "Voice note recorded" shows.
- For shot 11: tap Upload and capture the green success card.
- For shot 13: if no points, the empty state is fine — or let tracking run to show points.
- Backend note: maintenance mode must be OFF (`maintenance.enabled: false`) or you'll only see the maintenance screen. Confirm with WSL Kiro.
