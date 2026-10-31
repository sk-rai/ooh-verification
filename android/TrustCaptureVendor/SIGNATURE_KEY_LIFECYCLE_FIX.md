# Design Note — Signature Failures from Device Key Rotation (Coordinated Client + Server Fix)

**Status:** DESIGN ONLY — no code changed. For review by Android + Backend/Web agents and the owner before implementation.
**Severity:** High integrity issue. ~36% of photos fail real signature verification; legacy `photos.py` already hard-rejects them, so legitimate captures are being rejected in prod. Affects a live client (CorrXperts).

> **RECONCILED:** The Backend/Web agent produced a merged server-side design
> ("Device Key Versioning — Design Proposal" / `SIGNATURE_AUDIT_FINDINGS.md`).
> Both agents independently reached the same root cause and the same server-first
> historical-key-versioning fix. The server design is authoritative for the
> schema and verification helper; this note is authoritative for the Android
> (client) changes in §3B. Agreed reconciled names: table **`device_keys`**,
> **time-window model** (`active_from`/`active_to`, where `active_to = now()`
> retires a key — NOT a status enum).
>
> **Flagged back to Backend:** the server proposal's registration-flow pseudocode
> and backfill section still say `vendor_device_keys` + `status='active'/'retired'`,
> which contradict its own agreed `device_keys` + time-window schema. Those two
> sections should be updated to `device_keys` and set `active_to = now()` to retire.

---

## 1. Confirmed root cause

The capture → watermark → sign → store → upload pipeline is **byte-faithful and correct**. The failures are a **device-key-rotation / key-versioning** problem:

1. The Android signing key (`KeystoreManager`, alias `trustcapture_device_key`, ECDSA-P256, StrongBox/TEE) is regenerated **only when the Keystore alias is absent** — i.e. app reinstall, Clear Data, device restore/migration, or Keystore/StrongBox eviction. `generateKeyPairIfNeeded()` is a no-op when a key exists.
2. The key is built with `setUserAuthenticationRequired(false)` and no biometric-invalidation flags, so lockscreen/biometric changes do NOT rotate it. Only a true regeneration changes it.
3. **Re-registration of the new public key happens in exactly one place:** `AuthRepository.verifyOtp() → registerDeviceIfNeeded()` — the OTP path only. The device-attestation login path (`deviceLogin`) never re-registers.
4. Therefore, when a key is regenerated but the vendor does NOT go through a fresh OTP verify (they still have a session, or use device login), the app **silently signs new captures with the new private key while the server still holds the old registered public key.** Every capture after that point fails verification.
5. Server overwrites `vendors.public_key` on re-registration, orphaning all evidence signed under the previous key.

### Evidence (server-side, WSL)
- Failures concentrate on 2 vendors (EF48QB, 9BIZMV); 16 other vendors pass 100%.
- Each failing vendor shows a **single clean fail→pass boundary**. For test vendor 9BIZMV the boundary aligns to the minute with `vendors.public_key.updated_at` (device re-registered, captures began passing).
- Failures are NOT size-correlated (every ≥2MB photo passes), refuting the earlier watermark-recompression theory.
- `sha256(stored uploaded bytes) == stored file_hash` for all sampled rows → storage/transport is byte-faithful.

---

## 2. Why the obvious fix is insufficient

- **Freeze-the-artifact (sign the exact uploaded bytes):** good hygiene, but does NOT fix this — bytes already match.
- **Just re-register on every launch:** overwriting the server key again still orphans prior evidence. Re-registration alone, without historical key retention, permanently breaks verifiability of older captures. For a tamper-evidence product, historical keys MUST be retained.

---

## Fingerprint contract (CONFIRMED — client & server match)

Both sides compute the key fingerprint as **SHA-256 of the public key's DER
X.509 SubjectPublicKeyInfo (SPKI) bytes, lowercase hex, no separators.**
- Android (`KeystoreManager.getPublicKeyFingerprint()`): `sha256(publicKey.encoded)`
  — `PublicKey.getEncoded()` returns DER SPKI; `"%02x"` → lowercase hex.
- Server (`device_key_service.compute_key_fingerprint`): SHA-256 of DER-SPKI
  (base64-decode the PEM body to recover the identical DER bytes).
Same input bytes → identical fingerprint. The PEM the client sends in
`register-device` carries exactly these DER bytes (base64 of `publicKey.encoded`).
**One check item: confirm server emits LOWERCASE hex with no separators** to match
Android's `"%02x"`. If the server upper-cases or colon-separates, normalize before compare.

## Implementation status
- **Android (client §3B):** DONE (compiles, debug APK builds, Hilt OK). See §3B.
  Re-registration *navigation* (routing a capture-blocked vendor to the OTP screen)
  intentionally NOT wired yet — to line up with server deploy per sequencing.
- **Server (§3A):** DONE by Backend (warn-mode, append-only `device_keys`,
  real verification in `evidence.py`, startup DDL). Not yet deployed.

---

## 3. Proposed coordinated fix

### 3A. Server-side (Backend/Web — WSL) — REQUIRED, do first

1. **Historical key versioning.** Introduce a `device_keys` history table (or equivalent):
   - `vendor_id`, `device_id`, `public_key` (PEM), `key_fingerprint`, `active_from`, `active_to` (null = current), `created_at`.
   - On (re-)registration, INSERT a new row and close out the previous (`active_to = now`); do NOT destroy the old key.
2. **Stamp evidence with the signing key.** Add `key_fingerprint` (or `key_id`) to the photo/evidence rows at upload time, derived from the signature's verifying key, so each row records which key signed it.
3. **Verify against the correct historical key.** Verification should succeed if the signature validates against the key that was active at the row's capture time (or any historically-registered key for that device), not only the current key.
4. **Re-evaluate hard-reject.** Legacy `photos.py` hard-reject-on-invalid-signature should treat "valid under a prior registered key" as acceptable. Consider whether to re-score already-rejected historical rows once historical keys exist. (Note: rows signed under keys never registered cannot be recovered — true unknown keys.)
5. **Registration endpoint semantics:** make re-registration explicit and idempotent; record device_id + fingerprint so a repeat of the same key is a no-op and a changed key is versioned.

### 3B. Client-side (Android) — REQUIRED

1. **Detect actual key regeneration.** `generateKeyPairIfNeeded()` should return/signal whether it created a NEW key (vs found an existing one). On a genuine generation event:
   - Clear the local `isDeviceRegistered` flag.
   - Trigger re-registration of the new public key with the backend **before** any capture is allowed to sign/upload.
2. **Gate capture on key-registration state.** Do not sign-and-queue a capture while the current public key is not confirmed-registered with the server. If unregistered (e.g., key was just regenerated), route the vendor through re-registration first (OTP if the session can't otherwise re-register).
3. **Re-register on the device-login path too, when needed.** Today only `verifyOtp` re-registers. Add: if a key regeneration is detected, or if the server reports an unknown/again mismatched key, **route the vendor through OTP verification to re-register the new public key** (see policy decision below — OTP is required on every key regeneration).
4. **Optional integrity self-check:** on app start / before capture, compare local public-key fingerprint to the server's currently-registered fingerprint; if they differ, re-register.
5. **Audit:** log key-regeneration and re-registration events (the existing audit repo) so future divergence is traceable.

### 3C. Sequencing (because CorrXperts is live)

1. Ship **server-side historical key versioning first** (3A). This is backward-compatible and immediately stops orphaning: once deployed, a re-registration no longer destroys the ability to verify older evidence, and current failures for a device can be resolved by registering its current key as a new version.
2. Then ship the **Android re-registration + capture-gating** (3B) so new regenerations auto-recover without silent failures.
3. Backfill/re-score historical rejected rows only where a matching historical key exists.

---

## 4. Explicitly NOT the fix
- Not a watermark/compression change.
- Not a hashing/payload-format change (contract `photo_hash.hex().encode('utf-8')`, ECDSA-SHA256, base64 is correct).
- Not the freeze-the-artifact change (keep as separate hardening if desired, but it does not address these failures).

---

## 5. Policy decision (OWNER DECIDED)

**Re-registration identity proof: OTP is REQUIRED on every key regeneration.**
Decided by owner. When the device key regenerates (reinstall / clear-data /
device change / Keystore eviction), the vendor MUST complete an SMS OTP verify
before the new public key is registered and before any capture can sign/upload.
No authenticated silent re-register. Rationale: strongest identity proof for a
tamper-evidence product; prevents a compromised session from registering an
attacker-controlled key.

**Client implications of this decision:**
- On detected key regeneration → clear `isDeviceRegistered`, force the OTP flow
  (`requestOtp` → `verifyOtp` → `registerDeviceIfNeeded`) before capture is allowed.
- The device-login (attestation) path must NOT silently re-register; if it detects
  a regenerated/mismatched key, it drops the vendor to the OTP screen.
- Capture is gated until the current public-key fingerprint is confirmed-registered.

## 6. Open items / caveats
- Historical public keys are NOT retained today, so already-orphaned evidence signed under now-unknown keys cannot be retroactively verified. Versioning prevents future loss; it cannot fully recover the past unless an old key copy is found.
- EF48QB (2026-10-24) and 9BIZMV (2026-10-28) device re-registration timestamps CONFIRMED by Backend — aligns with each vendor's fail→pass boundary. Open item closed.

---

## 7. Temporary instrumentation to remove
The `SIGN_AUDIT` debug logging added during investigation (`SignAuditLog.kt`, and the guarded blocks in `PhotoSigner.kt` and `UploadManager.kt`) should be reverted before shipping any fix, unless we keep a trimmed version for key-fingerprint logging.
