# TrustCapture Android Demo — Comprehensive Shot List & Capture Guide

## Target Canvas
**Portrait, 1080×2340** — all frames fit+padded to one canvas. No landscape mixing.

## Capture Command
```powershell
cd C:\Users\SANTOSH\Documents\Photo_verification\android\TrustCaptureVendor
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" exec-out screencap -p > android-demo-shots\NN-name.png
```

---

## Full Journey — Both Routes, All Capture Types

The app has TWO capture routes that converge on the same camera/review screens:
- **Route A: Campaign** — Home → My Campaigns → Locations → Camera
- **Route B: Quick Capture** — Home → Quick Capture → Category picker → Camera

And the camera supports **photo + video**, each with **voice note + text note** on review.

### SECTION 1 — Onboarding & Auth (4 shots)
| # | Filename | Screen | Caption | Narration |
|---|----------|--------|---------|-----------|
| 01 | `01-privacy.png` | Privacy consent | "Transparent consent before any data is collected" | "Every TrustCapture session begins with clear, GDPR-aligned consent. The vendor sees exactly what is collected and why." |
| 02 | `02-login.png` | Login (Vendor ID + Phone) | "Sign in with your assigned Vendor ID" | "Each vendor is issued a unique ID by their organization. They enter it with their phone number to begin — no passwords to manage or leak." |
| 03 | `03-otp.png` | OTP verification | "A one-time passcode verifies the phone" | "A one-time passcode, sent by SMS, confirms the vendor owns the number. The device is then bound to a hardware-backed signing key, so future sign-ins need no SMS." |
| 04 | `04-home.png` | Home screen | "Two paths: assigned campaigns or quick capture" | "The home screen offers two paths. Capture against an assigned campaign, or quick-capture for spontaneous evidence." |

### SECTION 2 — Campaign Route (3 shots)
| # | Filename | Screen | Caption | Narration |
|---|----------|--------|---------|-----------|
| 05 | `05-campaigns.png` | My Campaigns list | "Campaigns assigned to this vendor" | "Vendors see only the campaigns assigned to them, each with its own capture rules." |
| 06 | `06-locations.png` | Locations list | "Verified locations within a campaign" | "Within a campaign, every location carries its expected coordinates for on-site verification." |
| 07 | `07-campaign-camera-photo.png` | Camera, photo mode, GPS locked | "Capture with live GPS, compass, and sensors" | "At the point of capture, the app records GPS, compass heading, WiFi, cell towers, and environmental sensors — a multi-signal fingerprint." |

### SECTION 3 — Photo Capture & Review (5 shots)
| # | Filename | Screen | Caption | Narration |
|---|----------|--------|---------|-----------|
| 08 | `08-photo-review-watermark.png` | Review — watermarked photo + metadata | "Watermarked and cryptographically signed" | "Each photo is watermarked with location and time, then signed with the device key. Any later edit breaks the signature." |
| 09 | `09-photo-review-details.png` | Review — capture details (GPS, confidence, signed) | "A full evidence record, captured automatically" | "The review screen shows the complete record — coordinates, accuracy, confidence score, and signature status." |
| 10 | `10-text-note.png` | Review — text note typed | "Add written observations" | "Vendors can add written notes for context the photo alone cannot convey." |
| 11 | `11-voice-note-recording.png` | Review — voice note recording | "Record a voice note on site" | "Or record a voice note on site, capturing verbal detail in the moment." |
| 12 | `12-voice-note-recorded.png` | Review — voice note recorded chip | "Voice note attached" | "The voice note attaches directly to the evidence record." |

### SECTION 4 — Upload (2 shots)
| # | Filename | Screen | Caption | Narration |
|---|----------|--------|---------|-----------|
| 13 | `13-uploading.png` | Review — uploading state | "Instant on-device save" | "On upload, evidence saves instantly to encrypted on-device storage." |
| 14 | `14-upload-success.png` | Upload success card | "Background upload — no waiting" | "It then uploads in the background, so vendors never wait on a slow network, and nothing is ever lost." |

### SECTION 5 — Video Capture (3 shots)
| # | Filename | Screen | Caption | Narration |
|---|----------|--------|---------|-----------|
| 15 | `15-video-mode.png` | Camera — video mode (before record) | "Switch to video for continuous proof" | "Switching to video mode captures continuous proof." |
| 16 | `16-video-recording.png` | Camera — recording (REC + timer) | "GPS tracked second-by-second" | "During recording, a GPS track is logged second by second, proving the vendor's path throughout the clip." |
| 17 | `17-video-review.png` | Review — video thumbnail + GPS track | "Video evidence, signed and tracked" | "The resulting video is signed just like a photo, with its GPS track bundled in." |

### SECTION 6 — Quick Capture Route (2 shots)
| # | Filename | Screen | Caption | Narration |
|---|----------|--------|---------|-----------|
| 18 | `18-quick-capture-categories.png` | Quick Capture category picker | "Spontaneous evidence, no campaign needed" | "For spontaneous events, Quick Capture needs no campaign — the vendor just picks a category." |
| 19 | `19-quick-capture-camera.png` | Quick Capture camera | "The same trusted capture pipeline" | "From there, the same trusted capture pipeline applies — full sensors, watermark, and signature." |

### SECTION 7 — Config (1 shot)
| # | Filename | Screen | Caption | Narration |
|---|----------|--------|---------|-----------|
| 20 | `20-settings.png` | Settings — Account / Security / About sections | "Backend-configurable behavior" | "Nearly every behavior — capture limits, branding, feature availability — is controlled from the backend. Policy changes need no app update." |

> Note: Tracking shots (My Route Today) are omitted because `features.tracking` is off in the live config. If enabled later, add `21-my-route.png` back.

---

## Closing Card
**"TrustCapture — trusted evidence for field operations"**

---

## Capture Order Tips
- **01-04:** Fresh install → consent → login → OTP → home (sequential)
- **05-07:** Tap My Campaigns → a campaign → a location → camera (wait for GPS "Ready"/"OK" so sensor chips populate)
- **08-14:** Take a photo → on review screen capture watermark/details, then type text note (10), start voice recording (11), stop it (12), tap Upload (13 = uploading, 14 = success)
- **15-17:** Back to camera → toggle video mode (15) → record ~5s (16 while REC shows) → stop → review with thumbnail (17)
- **18-19:** Home → Quick Capture → category grid (18) → pick one → camera (19)
- **20:** Settings gear (20) — shows Account, Device Security, About sections

## Pre-capture Checklist
- Backend `maintenance.enabled` is **false** ✅ (confirmed live) — no maintenance screen.
- GPS must be locked for shots 07, 16, 19 (sensor chips populated).
- Use a real photo for 08/09 so the watermark is genuine.
- Use a real registered Vendor ID + phone that can receive the SMS OTP.
- 20 shots total + closing card = 21 segments.
