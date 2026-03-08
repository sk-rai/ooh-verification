# OOH Vendor Photo Fraud Prevention

A tamper-proof photo verification system for Out-of-Home (OOH) advertising campaigns.

## 🎯 Problem Statement

OOH agencies lose 15-20% of campaign budgets when vendors submit edited/reused photos with spoofed GPS/timestamps. Manual verification of 800+ images per campaign is impossible at scale.

## ✨ Solution

Prevent fraud at capture — not detect it after upload. Force vendors to take live photos only with tamper-proof proof burned visibly into the image.

## 📱 Features

- **Campaign Code Authentication**: Vendors must enter valid campaign code before capture
- **Forced Live Capture**: Gallery uploads blocked — only live camera capture allowed
- **Tamper-Proof Watermark**: GPS + timestamp + campaign code burned into pixels
- **Visible Verification**: Any edit visibly corrupts the watermark

## 🚀 Quick Start

### View Locally

1. Clone or download this repository
2. Open `index.html` in your browser
3. Navigate through the 3-screen flow

### Deploy to GitHub Pages

1. Create a new GitHub repository
2. Push these files to the repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```
3. Go to repository Settings → Pages
4. Select "main" branch as source
5. Your app will be live at: `https://YOUR_USERNAME.github.io/YOUR_REPO/`

## 📸 How It Works

1. **Screen 1**: Vendor enters campaign code (e.g., RURAL-MP-2026)
2. **Screen 2**: Camera-only view — gallery access blocked
3. **Screen 3**: Photo captured with visible watermark containing:
   - GPS coordinates with accuracy
   - Timestamp (IST timezone)
   - Campaign code

## 🔒 Security Features

- GPS + timestamp burned into pixels (not EXIF metadata)
- Visible watermark makes tampering obvious
- No gallery access during capture
- Real-time location verification

## 💡 Value Proposition

"GPS + timestamp burned visibly into pixels — not hidden in EXIF metadata. Any edit visibly corrupts the watermark, making fraud obvious in 3 seconds."

## 🛠️ Tech Stack

- Pure HTML5, CSS3, JavaScript
- No dependencies or frameworks
- Works on all modern browsers
- Mobile-first Android Material Design

## 📝 Next Steps

This is a frontend prototype for client review. Full production app would include:
- Backend API for campaign validation
- Photo upload and storage
- Admin dashboard for verification
- Vendor management system
- Analytics and reporting

## 📄 License

Proprietary - All rights reserved
