# Device Key Versioning — Design Proposal

Status: PROPOSAL (analysis + design only — no code changed). Fixes the root cause
behind the ~36% signature "failures" (see SIGNATURE_AUDIT_FINDINGS.md).

## Problem (confirmed)

Each vendor has ONE `vendors.public_key` column. On device re-registration the
backend OVERWRITES it:

    backend/app/api/auth.py:353   vendor.public_key = data.public_key

Every past evidence row was signed with whatever key was current at capture time.
After an overwrite, all prior evidence verifies against the WRONG (new) key and
fails. Confirmed on prod: vendors EF48QB and 9BIZMV each show a single clean
fail→pass boundary aligned to a key change; all other vendors (no re-registration)
pass 100%. The signing/watermark/storage pipeline is correct.

Consequences today:
- Legacy `photos.py` hard-rejects on invalid signature → legitimate older captures
  got rejected after any device re-registration.
- The new `evidence.py` only does a non-empty check, so it never noticed — but it
  also can't honestly verify.
- Historical evidence is PERMANENTLY unverifiable once the key is overwritten
  (the old public key is gone).

## Design goals

1. Preserve verifiability of ALL evidence for the life of the record, across any
   number of device re-registrations (critical for a tamper-evidence product).
2. Make verification deterministic: each evidence row is checked against the key
   that was active WHEN IT WAS SIGNED, not "the latest key."
3. Backward compatible: existing rows (which only have the current key) must not
   break further; migrate what we can, degrade honestly for the rest.
4. No behavioural surprise for the live client (CorrXperts): don't start
   hard-rejecting more than today without an explicit decision.

## RECONCILED WITH ANDROID DESIGN NOTE

Both agents independently reached the same root cause, the same "historical key
versioning, server-first" fix, and the same rejection of freeze-the-artifact /
re-register-only as insufficient. This doc is the MERGED agreed design. Reconciled
points:
- Table name: use **`device_keys`** (Android's name) — not `vendor_device_keys`.
- Use a **time-window model** (`active_from` / `active_to`) rather than a
  status enum — it maps directly to "verify against the key active at capture time."
- NEW critical detail from Android (explains the silent divergence): the app
  re-registers the public key ONLY on the OTP path
  (`verifyOtp → registerDeviceIfNeeded`); the device-login path never re-registers.
  So after a key regeneration, a vendor who keeps a session / uses device-login
  signs with the NEW private key while the server still holds the OLD public key —
  silent failures until a fresh OTP. The CLIENT fix (capture-gating +
  re-register-on-device-login) is therefore REQUIRED, not optional.
- Android key facts: `KeystoreManager`, alias `trustcapture_device_key`,
  ECDSA-P256, StrongBox/TEE, `setUserAuthenticationRequired(false)` (lockscreen/
  biometric changes do NOT rotate it). Regeneration happens only when the alias is
  absent: reinstall / Clear Data / restore-migration / Keystore eviction.

## Proposed schema

New table: `device_keys` (append-only history of registered keys, time-windowed).

```sql
CREATE TABLE IF NOT EXISTS device_keys (
    key_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id     VARCHAR(6) NOT NULL REFERENCES vendors(vendor_id) ON DELETE CASCADE,
    tenant_id     UUID NOT NULL,
    device_id     VARCHAR(255),
    public_key    TEXT NOT NULL,
    algorithm     VARCHAR(50) NOT NULL DEFAULT 'ECDSA-P256',
    key_fingerprint VARCHAR(64) NOT NULL,   -- SHA-256 of the normalized PEM public key
    active_from   TIMESTAMPTZ NOT NULL DEFAULT now(),
    active_to     TIMESTAMPTZ,              -- NULL = current active key
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_device_keys_vendor ON device_keys (vendor_id);
CREATE INDEX IF NOT EXISTS ix_device_keys_fingerprint ON device_keys (key_fingerprint);
CREATE INDEX IF NOT EXISTS ix_device_keys_vendor_window ON device_keys (vendor_id, active_from, active_to);
```

Verification "key active at capture time" = the `device_keys` row for that vendor
where `active_from <= capture_time AND (active_to IS NULL OR capture_time < active_to)`.
Fallback: try all of the vendor's keys newest→oldest (covers clock skew / the brief
regenerate-mid-session window Android described).

Stamp each evidence row with the key it was verified against (so it's queryable
and immutable):

```sql
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS signing_key_id UUID;      -- FK device_keys.key_id
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS signing_key_fingerprint VARCHAR(64);
-- (photos legacy table: optional parallel columns if we want legacy coverage)
```

Keep `vendors.public_key` as a convenience pointer to the CURRENT active key
(denormalised, so existing reads keep working), but it is no longer the source of
truth for historical verification — `device_keys` is.

Provision via the project's established pattern: `main.py` startup
`CREATE TABLE/INDEX/ALTER ... IF NOT EXISTS` (matches task_queue/evidence/
vendor_tracks), AND a committed Alembic migration for a clean record. (The repo
currently relies on startup DDL for newer tables; do both for hygiene.)

## Registration flow change (auth.py register-device)

Instead of overwriting (time-window model, table `device_keys`):

```
# OLD
vendor.public_key = data.public_key

# NEW (append + point)
fp = sha256(DER_SPKI_bytes(public_key))      # see fingerprint contract below
active = SELECT * FROM device_keys
           WHERE vendor_id=? AND active_to IS NULL
if active and active.key_fingerprint == fp:
    pass                         # same key re-sent, no-op (idempotent)
else:
    if active:
        UPDATE device_keys SET active_to = now()
            WHERE key_id = active.key_id          # retire previous by closing window
    INSERT device_keys (vendor_id, tenant_id, device_id, public_key,
        algorithm, key_fingerprint, active_from=now(), active_to=NULL)
vendor.public_key = data.public_key   # keep denormalised current-key pointer
```

### FINGERPRINT CONTRACT (cross-component — must match Android exactly)
`key_fingerprint = sha256( DER SubjectPublicKeyInfo bytes ) -> lowercase hex`.
Android computes SHA-256 over `publicKey.encoded` (X.509 SPKI DER). The server
receives the key as PEM, so it MUST base64-decode the PEM body (strip
`-----BEGIN/END PUBLIC KEY-----` and newlines) to recover the DER bytes, then
hash THOSE. Do NOT hash the PEM string. If this diverges, the client's divergence
check cannot be cross-checked server-side.

Append-only: we NEVER delete an old key, so old evidence stays verifiable.

## Verification change (unify evidence.py + photos.py + /v1/verify)

One helper, used everywhere:

```
def verify_evidence_signature(vendor_id, photo_hash_bytes, signature_bytes, algorithm):
    # 1. If the evidence row already has signing_key_id, verify against THAT key only.
    # 2. Else (new capture / legacy), try the vendor's keys in order:
    #       active key first, then retired keys (newest→oldest).
    #    On success, record which key_id/fingerprint matched.
    # 3. Return (valid: bool, matched_key_id, matched_fingerprint).
```

- New captures: verify against active key; stamp `signing_key_id` on the evidence
  row at insert. (Normally matches active key; the brief window where a device
  re-registers mid-session is covered by also trying retired keys.)
- Historical re-verification (reports, audits): verify against the row's
  `signing_key_id` if set, else fall back to trying all the vendor's known keys.

This replaces:
- `evidence.py:347` non-empty check → real verification via the helper.
- `photos.py` single-key verify → helper (keeps legacy coverage).
- `verify_api.py` shallow scorer → (separate item, but should use the same core).

## Backfill / migration strategy

We cannot resurrect public keys that were already overwritten. But we CAN:
1. Seed `device_keys` from the current `vendors.public_key` for every vendor
   (active_to=NULL, active_from = vendor.updated_at as best estimate).
2. For existing evidence that verifies against the current key → stamp its
   `signing_key_id` with that key.
3. For existing evidence that FAILS against the current key (the orphaned ~36%):
   mark `signing_key_fingerprint = NULL` / `signing_key_id = NULL` and a status
   like `unverifiable_key_rotated` rather than `rejected`. This is the honest
   state: "validly signed under a key we no longer hold," NOT "fraud."
   - Requires a new nuance in status handling (see below).

## Status-handling nuance (IMPORTANT — live client)

Today: invalid signature → hard reject (legacy) / ignored (evidence). Neither is
right for key-rotated evidence. Proposed statuses for the signature dimension:
- `signature_verified` — matched a known key.
- `signature_unverifiable_rotated` — vendor has re-registered; the signing key is
  no longer held. NOT fraud; present as "integrity key rotated" rather than
  rejected. Confidence scoring should treat this as neutral/needs-review, not an
  automatic reject.
- `signature_invalid` — a known key exists for the capture window but the signature
  does not verify (genuine tamper/mismatch) → this is the real reject case.

This requires distinguishing "no key to check against" from "checked and failed."
Recommend NOT auto-hard-rejecting the rotated bucket (that's what's been wrongly
rejecting CorrXperts' legitimate older captures).

## Android coordination (CONFIRMED REQUIRED — from Android design note §3B)

The server fix alone is necessary but NOT sufficient, because the app only
re-registers on the OTP path. Android will:
1. Make `generateKeyPairIfNeeded()` signal when it creates a NEW key; on a genuine
   generation, clear `isDeviceRegistered` and re-register BEFORE any capture signs.
2. Gate capture on confirmed key-registration state (don't sign/queue while the
   current public key isn't confirmed-registered).
3. Re-register on the device-login path too (not just OTP) when a regeneration is
   detected or the server reports a key mismatch.
4. Optional: on app start, compare local key fingerprint to the server's current
   registered fingerprint; re-register on mismatch.
5. Send stable `device_id` + key fingerprint so the server correlates device↔key.

## Confirmed vendor timestamps (closes Android open item)

- EF48QB: `updated_at`/`last_login_at` = 2026-10-24 03:18 → matches its fail→pass
  boundary (failed ≤10-23, passed from 10-24). OTP re-registration on Oct 24.
- 9BIZMV: `updated_at` = 2026-10-28 15:14 → matches its boundary (passed from 15:15).
Both boundaries align to the hour with the vendor's key-overwrite timestamp.
Root cause fully confirmed for both failing vendors.

## Open policy decision — CLOSED (owner confirmed Oct 31 2026)

**OTP is required on every key regeneration. No authenticated silent re-register.**

Rationale: key regeneration (reinstall / Clear Data / device restore / Keystore
eviction) is a significant security event; requiring a fresh OTP ensures identity
is re-verified at that point regardless of existing session state.

Android shipped this in 1.5.0 (commit c2bba54): on key-regen detection →
capture gated → "Re-register with OTP" UX shown → OTP flow → new key registered.
No silent re-register path was implemented.

## Android cleanup before shipping
Revert the temporary SIGN_AUDIT debug instrumentation (`SignAuditLog.kt` and the
guarded blocks in `PhotoSigner.kt` / `UploadManager.kt`), or keep a trimmed
key-fingerprint-only log.

## IMPLEMENTATION STATUS (server-side) — built, verified, NOT committed/deployed

Done this session (local only, self-tested, no DB writes, nothing pushed):
- `app/models/device_key.py` — DeviceKey model (append-only, time-windowed).
- `app/models/__init__.py` — register DeviceKey.
- `app/models/evidence.py` — added signing_key_id / signing_key_fingerprint /
  signature_outcome columns.
- `app/services/device_key_service.py` — compute_key_fingerprint (DER-SPKI SHA-256,
  the contract Android must match), register_key_version (append-not-overwrite,
  idempotent on same fingerprint), get_keys_for_vendor, _key_active_at (time-window),
  verify_against_history (warn-mode outcomes).
- `app/api/auth.py` register-device — appends a key version instead of overwriting
  vendors.public_key (request/response unchanged; non-fatal history write).
- `app/api/evidence.py` — photo path now does REAL signature verification against
  key history in WARN MODE: computes signature_outcome, stamps the evidence row,
  and only treats outcome=="invalid" (genuine mismatch) as a signature failure.
  "verified" is valid; "unverifiable_rotated"/"no_keys" are NEUTRAL (never newly
  hard-reject legitimate rotated captures).
- `app/main.py` — startup DDL creates device_keys + evidence key-stamp columns.

Self-tests passed: fingerprint deterministic across PEM whitespace + key-sensitive;
time-window key selection correct; full import/compile of all changed modules.

DECISION APPLIED: backfill SKIPPED (per owner) — only correct historical orphaned
rows if CorrXperts asks. New captures get full key-history verification going forward.

NOT DONE (future / separate): legacy photos.py still hard-rejects (unchanged this
pass); /v1/verify still shallow; no tests added yet; backfill script not written.

## Rollout plan (gated, non-breaking)

1. Add `device_keys` + evidence key columns (startup DDL + migration).
2. Change register-device to append-not-overwrite; backfill current keys.
3. Introduce the unified verify helper; wire evidence.py to real verification in
   WARN mode (record result, do NOT hard-reject) — matches the earlier decision.
4. Backfill `signing_key_id` on historical evidence; bucket the orphaned rows as
   `signature_unverifiable_rotated` (not rejected).
5. Review legacy photos.py hard-reject to stop rejecting the rotated bucket.
6. Only AFTER confidence is high + Android confirms: consider enforcing
   `signature_invalid` (genuine mismatch) as reject, keeping rotated as neutral.

## Tests (currently none for this path — add)
- Register device → sign → verify PASS.
- Re-register with NEW key → OLD evidence still verifies against retired key;
  NEW evidence verifies against active key.
- Tampered signature with a known active key → `signature_invalid`.
- Vendor with only a rotated key, old evidence → `signature_unverifiable_rotated`,
  not rejected.
- Backfill idempotency.

## Out of scope (separate backlog items)
- `/v1/verify` real pipeline + rate-limit/scope enforcement (should reuse the
  unified verify core once it exists).
- Hash-chain extension to all evidence types.
```
