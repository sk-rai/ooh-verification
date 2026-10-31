# Dev Test — Device Key Lifecycle Fix (end-to-end)

Validates the coordinated client + server fix for the signature-key-rotation issue,
on the DEV backend, before any prod deploy.

## Prerequisites (ORDER MATTERS)
1. **WSL deploys the server change to DEV first** (`ooh-verification.onrender.com`).
   The debug APK targets this backend. Until it's deployed, the APK hits the OLD
   server (no `device_keys` table) and the test is meaningless.
   - Confirm with WSL: `device_keys` table exists + evidence key-stamp columns provisioned
     (startup DDL), and register-device now appends instead of overwrites.
2. **Debug APK (key-lifecycle build):**
   `C:\Users\SANTOSH\OneDrive\Documents\TrustCapture-debug-keyfix.apk`
   (built from branch `fix/device-key-lifecycle`; targets the dev backend).

## Install
- Transfer the APK to the phone (USB / Drive / email) and install, OR via adb:
  `adb install -r "C:\Users\SANTOSH\OneDrive\Documents\TrustCapture-debug-keyfix.apk"`
- This debug build **replaces** the prod app (same applicationId). Reinstall prod later.

---

## Scenario A — Happy path (fresh registration → capture verifies)
1. Launch the app. If first run, complete privacy consent.
2. Log in with a TEST vendor via **OTP** (dev backend). This generates the device
   key and registers it → creates the FIRST `device_keys` row for this vendor.
3. Open a campaign (or Quick Capture) and **capture 1 photo**; let it upload.
4. **WSL verifies server-side** for that vendor's newest evidence row:
   - `signature_outcome = verified`
   - `signing_key_id` + `signing_key_fingerprint` stamped
   - the fingerprint equals the one the app registered (DER-SPKI SHA-256, lowercase hex)

**PASS criteria:** outcome = verified, key stamped, fingerprints match.

---

## Scenario B — Key regeneration → capture blocked → re-register
This reproduces the real-world failure and proves the fix recovers it.
1. With the app already registered (after Scenario A), go to the phone's
   Settings → Apps → TrustCapture → Storage → **Clear storage / Clear data**.
   (This deletes the Keystore-backed key state the same way a reinstall/restore does.)
2. Relaunch the app and try to reach the camera (open a campaign / Quick Capture).
3. **EXPECTED (client fix):** capture is BLOCKED with the screen
   **"Re-registration Required"** and a **"Re-register with OTP"** button
   (reason: the device key changed and must be re-registered).
4. Tap **"Re-register with OTP"** → you're routed to the login screen → complete OTP.
   This re-registers the NEW public key → server APPENDS a new `device_keys`
   version and retires the previous one (does NOT overwrite/orphan).
5. Capture a new photo; let it upload.
6. **WSL verifies server-side:**
   - the vendor now has **2 `device_keys` rows**: the old one retired
     (`active_to` set), the new one active (`active_to = NULL`).
   - the NEW evidence row → `signature_outcome = verified` against the ACTIVE key.
   - any OLD evidence (from Scenario A) → still `verified` against the RETIRED key
     (historical verifiability preserved — the whole point of versioning).

**PASS criteria:** capture blocked on regen; OTP re-register appends a key version;
new evidence verifies against active key; old evidence still verifies against retired key.

---

## What this proves
- Client detects key regeneration and refuses to silently sign with an unregistered
  key (the bug that caused the ~36% failures).
- OTP re-registration is enforced (owner policy).
- Server retains historical keys → prior evidence stays verifiable across rotations.
- No legitimate capture is hard-rejected (warn-mode).

## Notes / gotchas
- Use a TEST vendor on dev, not a live CorrXperts vendor.
- Fingerprint must match EXACTLY: `sha256(DER SubjectPublicKeyInfo)`, lowercase hex,
  no separators. If server emits uppercase/colons, normalize before compare.
- If capture is NOT blocked after Clear Data, check: did the app actually regenerate
  the key (new fingerprint) and did `registeredKeyFingerprint` get cleared? WSL/me to
  inspect logs. (The debug build no longer writes the SIGN_AUDIT file — that was reverted.)
