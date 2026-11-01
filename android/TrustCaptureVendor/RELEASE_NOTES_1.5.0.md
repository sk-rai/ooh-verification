# Release Notes — TrustCapture Vendor 1.5.0 (versionCode 15)

**Status:** Ready to build and upload.
**Previous production release:** 1.4.1 (versionCode 14)
**Package:** `com.lynksavvy.trustcapture`
**targetSdk / compileSdk:** 36 (unchanged from 1.4.1)

---

## Play Store "What's new" (paste into Play Console release)

```
Security: device re-registration now preserves the integrity of previously
captured evidence. App reinstalls and device migrations no longer invalidate
prior photo verification records. Stability improvements.
```

---

## Full changelog (1.4.1 → 1.5.0)

### Security fix (root-cause: ~36% signature verification failures)
Root cause confirmed: when a device key regenerated (reinstall / clear-data /
device migration / Keystore eviction), the app silently signed new captures with
the new private key, but the server still held the old registered public key.
Every capture after that point failed server-side signature verification.

**Client-side (this release):**
- `KeystoreManager.generateKeyPairIfNeeded()` now signals when a NEW key was
  actually generated vs. finding an existing one.
- `AuthRepository` records the fingerprint of the registered key (SHA-256 of DER
  SubjectPublicKeyInfo, lowercase hex). On next app start, detects if the current
  device key differs from the registered one (i.e. a regeneration occurred).
- `CameraViewModel` gates capture: if the current key is not registered, capture
  is blocked with a clear message and a "Re-register with OTP" action.
- Tapping "Re-register with OTP" logs out and routes the vendor through the OTP
  flow, which re-registers the new public key with the backend.
- Backward-compatible: existing installs without a stored fingerprint are backfilled
  on first check (not falsely blocked).

**Server-side (deployed separately by Backend/Web, commit f097adb):**
- New `device_keys` table: append-only, time-windowed key history per vendor.
  Re-registration APPENDS a new key version and retires the old one; never deletes.
- `evidence.py`: real ECDSA signature verification in warn-mode. Verifies each
  photo against the key active at capture time. Old evidence verified against
  the retired key — not orphaned.
- Stamps `signing_key_id`, `signing_key_fingerprint`, `signature_outcome` per row.
- `unverifiable_rotated` (key rotated, old key not retained) = neutral, not rejected.
- Only `signature_invalid` (genuine mismatch with key coverage) is a failure.

### End-to-end test confirmation (pre-release, dev backend)
- Photo 1 (captured before Clear Data): `outcome=verified`, key=`7091525e` ✅
- Photo 2 (captured after key regen + OTP re-register): `outcome=verified`, key=`70dbd960` ✅
- Both keys retained in `device_keys` history. Old evidence NOT orphaned. ✅

---

## Policy (owner-confirmed)
OTP required on every key regeneration. No authenticated silent re-register.

## Build note
- versionCode 13 and 14 were consumed by earlier upload attempts. versionCode 15 is
  the correct next value (vc14 = 1.4.1 is the current live Production release).
- Check Play Console for the highest used versionCode before building any future
  release.
