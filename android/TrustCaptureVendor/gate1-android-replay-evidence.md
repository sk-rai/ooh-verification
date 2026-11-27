# Gate 1 Android replay evidence for re-review

Reviewed source baseline: `codex/gate1-android-handoff` at `f1fe878058831c1c9a80f5bf60b7ef34c4738e3e`. The run used the Pixel 6 emulator and the staging-only lost-response debug APK with application ID `com.lynksavvy.trustcapture.gate1`. Re-review is limited to synthetic evidence recovery for the reservation below. The Android session used manual photo sync. Production remains on hold.

The reviewed database is **Room v13**. SQLCipher remains the open-helper factory, and the registered path from the verified Play v15 / Room v10 baseline is **10 → 11 → 12 → 13**. The emulator staging package was a side-by-side install. It did not exercise this signed migration path. [Database version](app/src/main/java/com/trustcapture/vendor/data/local/db/AppDatabase.kt#L14) · [Migration registration](app/src/main/java/com/trustcapture/vendor/di/DatabaseModule.kt#L45)

## Reservation-specific timeline

| Checkpoint | Preserved evidence |
| --- | --- |
| Fresh capture | Observation 2 required photo slot. Local capture ID `dfd780dd-5ae2-4eb3-94f2-3765b4a9989a`. Original media SHA-256 `a6a2d578d685ec80308060b4602a222ac5d0ad7e6ab955eb8cb9fa039b0c5ed2`. |
| First response dropped | On Nov 27 at 14:21:05.214, `Gate1Evidence` logged `Dropped committed finalization response; reservation=05847036-a9ba-415e-baff-813c4f9d3375` (PID 8636). The staging interceptor logs this only when the new finalization returns **HTTP 201** and its one-shot switch is armed. It closes the response and throws before the repository receives an acknowledgement. [Drop condition](app/src/main/java/com/trustcapture/vendor/ui/inspection/InspectionStagingSmokeScreen.kt#L77) |
| Force-stop and sign-in | ADB force-stopped and reopened the app. A second `sha256sum` returned the same media hash and capture ID filename. The operator signed in again. The screenshot showed passed enrollment and both observations on screen. The next trace was from PID 8935. |
| Evidence-only retry | The response-drop control was off. The operator session used **Sync saved photos** with the saved queue. There was no new capture or form submission. At 14:23:47.450 the acknowledgement trace recorded reservation `05847036-a9ba-415e-baff-813c4f9d3375`, receipt `885e32d3-1f91-434f-811f-65913aed28b4`, evidence `0af9160b-d1c2-5cac-94c4-dc5ce22bd9c1`, and `eligible=true`. The trace is emitted after the conditional Room acknowledgement succeeds. |
| Cleanup after acknowledgement | At 14:23:47.476, the same PID and reservation logged `Media cleanup checked; present=false`. The UI reported 2 complete, 0 pending retry, 0 held, including the earlier normal capture. [Acknowledgement and cleanup ordering](app/src/main/java/com/trustcapture/vendor/domain/repository/InspectionEvidenceRepository.kt#L43) |
| WSL PostgreSQL read-back | Supplied result for this reservation: `receipt_rows=1`, `matching_evidence_rows=1`, `exact_replay_matches=1`. WSL matched the replay receipt and evidence IDs and confirmed the exact binding to **Observation 2 → photo**. |

### Evidence gaps

- The device trace did not record a SHA-256 of the exact finalization request on each attempt. The photo SHA-256 above is a separate measurement. The source preserves and resends the saved request, and the offline mock compares the two request bodies byte-for-byte, but those do not supply device request hashes. [Mock retry test](app/src/test/java/com/trustcapture/vendor/InspectionCaptureSyncTest.kt#L30)
- Initial receipt and evidence IDs were not captured on Android because the response was deliberately closed before decoding. The database read-back corroborates one committed result and matches the replay IDs. The device trace did not separately log the replay HTTP status.
- No raw OTP, token, enrollment proof, or credential is included. The evidence above is a transcription of the observed filtered logs and operator reports. No staging run was repeated for this bundle.

## Supporting acceptance traces

| Check | Sanitized evidence and limits |
| --- | --- |
| Sign-in, enrollment, and item-two render | Staging operator reported verify OTP **200**, inspection enrollment **201**, package **200**. The fixed emulator trace at 12:04:38–39 shows one package effect, decoded **200**, package cached, and inspection ready to render. The screenshot shows sign-in and enrollment passed, Observation 1 and Observation 2 visible, and the required photo on Observation 2. Separate auth-response Logcat lines were not retained. |
| Normal capture and sync | Emulator opened Observation 2’s slot and took a synthetic camera photo. UI reported local save and then `1 complete, 0 pending retry, 0 held`. WSL reported exactly one receipt and evidence record `1d4a66b0-adf5-541b-bb84-de0ac66e2517` bound to Observation 2 → photo. The normal run preceded the explicit acknowledgement/cleanup markers. Their ordering is directly traced on the lost-response run. |
| Read-only offline cold reopen | After force-stop, airplane mode was on and Wi-Fi off. **Open saved inspection** restored Observation 1 = `2.50` and Observation 2 = `3.75` with the required photo slot still on item two. Trace at 17:26:33–34 shows package effect started, package decoded from the offline path, and inspection ready to render. No OTP was needed. UI inspection confirmed no upload control and no enabled photo action. |

**Reviewer decision requested:** Issue a reservation-specific verdict on exact replay, local recovery, and acknowledgement-before-cleanup. Treat request hashes and initial client-visible commit IDs as absent evidence. Leave the signed v15 upgrade, background retry, and Android end-to-end submission open. GPS and production rollout remain on hold.
