# Gate 2 Kotlin golden-file harness proposal

**Status: proposal for agreement.** The Android reference is `codex/gate1-android-handoff` at `f1fe878`. Wait for the independent WSL review and shared fixture agreement before implementing the evaluator.

## Harness boundary

Use a standalone Kotlin/JVM module outside the Android app. It reads the same UTF-8 JSON files as the Python and TypeScript runners, evaluates a proposed versioned rules profile, and compares structural JSON output to checked-in expected output. The runners need no Android runtime, network, database, credentials, real media, or wall clock. Golden expectations are reviewed independently of all three implementations. Reject duplicate JSON keys at fixture ingestion so parser behavior cannot decide the result.

One runner invocation takes a fixture directory, runs files in lexicographic order, and exits nonzero with the file, case ID, and first differing JSON Pointer. Object member order is immaterial. Arrays have a specified order. Decimal strings, IDs, and enum values compare exactly. This is a semantic parity test. Signature verification, receipt expiry, authorization, persistence and server authority remain separate tests.

## Proposed shared envelope

Use one file per workflow, with a common pinned fixture and several cases. Each case states the complete answers and evidence set, plus its display order. Nothing carries over from a prior case. All IDs below are synthetic. The server issues repeat IDs through the pinned package. Display order must never change the binding or canonical submission order.

| Key | Contract to agree |
| --- | --- |
| `fixture_version`, `profile` | Version of the test input and evaluated rules. Reject unknown required capabilities with stable configuration errors before evaluating answers. |
| `package` | Fixed visit, assignment and generation, document instance, form version, ordered repeat IDs, field definitions, slot definitions and rules. Account scope is implicit in the synthetic fixture. The real backend reauthorizes it. |
| `cases[].answers` | Object keyed by repeat ID, then field ID. Absent field means missing. Explicit null, false, empty string and empty array remain distinct. |
| `cases[].receipts` | Synthetic receipt and evidence ID, eligibility, visit, assignment, generation, document, field, slot and repeat ID. The runner checks exact target identity and supplied eligibility. |
| `cases[].display_order` | UI-only order. Output projection follows pinned repeat order. Reject unknown or duplicate display IDs as malformed test input. |
| `cases[].expected` | Configuration errors, field and slot applicability, retained answers, ordered submission projection, accepted evidence bindings, stable field/member errors, and a `can_submit` Boolean. Use IDs and codes in expectations. Localized text is outside parity. |

### Example shared file fragment

```json
{
  "fixture_version": 1,
  "profile": "trustcapture-gate2-proposed-v1",
  "package": {
    "visit_id": "visit-brakes",
    "assignment_id": "assignment-brakes",
    "generation": 1,
    "document_instance_id": "document-brakes",
    "form_version_id": "brakes-v1",
    "required_capabilities": ["repeat-same-item", "conditional-photo"],
    "repeat_items": ["brake-a", "brake-b"],
    "fields": [
      {"id": "defect", "type": "boolean", "required": true},
      {"id": "notes", "type": "text", "visible_if": {"eq": [{"scope": "item", "field": "defect"}, true]},
       "required_if": {"eq": [{"scope": "item", "field": "defect"}, true]}}
    ],
    "slots": [
      {"id": "photo", "field_id": "defect", "required_if": {"eq": [{"scope": "item", "field": "defect"}, true]}}
    ]
  },
  "cases": [{
    "id": "photo-stays-on-b-after-display-reorder",
    "display_order": ["brake-b", "brake-a"],
    "answers": {"brake-a": {"defect": false, "notes": "retained"}, "brake-b": {"defect": true, "notes": "check"}},
    "receipts": [{
      "receipt_id": "receipt-b", "evidence_id": "evidence-b", "eligible": true,
      "visit_id": "visit-brakes", "assignment_id": "assignment-brakes", "generation": 1,
      "document_instance_id": "document-brakes", "field_id": "defect", "slot_id": "photo", "repeat_item_id": "brake-b"
    }],
    "expected": {
      "configuration_errors": [],
      "applicability": {
        "brake-a": {"notes": "inactive", "photo": "inactive"},
        "brake-b": {"notes": "required", "photo": "required"}
      },
      "retained_answers": {"brake-a": {"defect": false, "notes": "retained"}, "brake-b": {"defect": true, "notes": "check"}},
      "submission_projection": [
        {"repeat_item_id": "brake-a", "answers": {"defect": false}},
        {"repeat_item_id": "brake-b", "answers": {"defect": true, "notes": "check"}}
      ],
      "evidence_bindings": [{"repeat_item_id": "brake-b", "field_id": "defect", "slot_id": "photo", "evidence_id": "evidence-b"}],
      "errors": [],
      "can_submit": true
    }
  }]
}
```

The fixture uses readable synthetic IDs for illustration. Use UUID-shaped fixture values if the agreed profile requires UUID syntax. The projection is a diagnostic output even when `can_submit=false`. A consumer must not send an incomplete projection as a submission.

## Rule semantics to freeze

- Predicates are typed trees using explicit item references. A comparison on a missing, null or invalid operand is **unresolved**, except with an explicit presence/null test. Boolean false is a legitimate value. Use three-valued nested logic. `not(unresolved)` stays unresolved, `all` returns false if any operand is false, and `any` returns true if any operand is true. Otherwise unresolved propagates. A field with an unresolved visibility condition preserves its answer and is excluded from the projection. Unresolved applicability that affects submission blocks it with an ID.
- For an active required field, missing and null are distinct errors. A Boolean false passes. A required text empty string fails, with whitespace behavior to be agreed. An empty array remains a distinct provided value but is type-invalid for these controls. A hidden answer is retained locally, excluded from projection, and does not activate another field unless the profile explicitly allows that dependency. A hidden slot contributes no binding.
- Use decimal objects such as `{"value":"2.50","scale":2,"unit":"mm"}`. `value` is an exact ASCII decimal string, `scale` an integer, and `unit` an exact schema option. Do not coerce numeric JSON, exponent syntax, wrong precision, or units. Evaluate comparisons by exact decimal arithmetic if in scope. Keep calculations outside this PoC.
- A receipt can satisfy only the exact visit, assignment and generation, document, field, slot and repeat item with `eligible=true`. Report a receipt mismatch separately from an unsatisfied required slot. Reordering preserves the binding. A deleted or replaced target never borrows it.
- Configuration errors prevent evaluation and use stable identifiers such as `UNSUPPORTED_CAPABILITY` and `INVALID_FIELD_REFERENCE`. Field errors carry `code`, `document_instance_id`, `repeat_item_id`, and `field_id` or `slot_id`. Agree deterministic array ordering, for example pinned repeat and field order followed by code and evidence ID as tie-breakers. Example codes below are proposed.

## Golden expectations to instantiate

| Workflow and case | Expected result |
| --- | --- |
| Elevator brakes, reorder `B,A` with eligible photo on B | A false is valid. A notes stay in the draft and are omitted from projection. B’s notes and photo are required and satisfied. Projection order stays A,B. Receipt stays on B. Submission allowed. |
| Elevator brakes, A defect omitted or explicitly null | Omitted produces `ANSWER_REQUIRED`; explicit null produces `ANSWER_NULL`. A notes and photo are unresolved. No binding is inferred. Submission blocked with a stable unresolved-condition code. |
| Elevator brakes, B defect true and notes empty string | Notes active and required, `ANSWER_EMPTY` for B only. Empty array in the same field produces `ANSWER_TYPE`. Neither affects A. |
| Elevator brakes, wrong target | Run four separate cases changing only document, slot, repeat item, or assignment generation on B’s receipt. Each reports `EVIDENCE_TARGET_MISMATCH` and `REQUIRED_EVIDENCE_MISSING` on B. An exact ineligible receipt yields `EVIDENCE_INELIGIBLE` and the same missing slot. |
| Pipeline, `P1` PASS and `P2` FAIL | Both use valid fixed-scale mm readings. P1’s previously entered severity stays in local answers and is omitted from projection. P2’s severity and photo are required. An eligible exact photo and a valid severity option allow submission. Use synthetic magnitudes without pass/fail thresholds. |
| Pipeline, `P2` FAIL → PASS | Keep P2’s severity and photo reference locally. Omit severity and inactive evidence from projection. A later reversal restores them only for the unchanged exact target and eligible receipt. |
| Pipeline, `P2` N/A | N/A is a distinct enum, not null or false. Proposed fixture requires an explanation and omits the measurement and photo from projection. If explanation is missing, emit `ANSWER_REQUIRED` for its field. |
| Pipeline, decimal and unit rejection | With an active mm field at scale 2, accept `"2.50"`. Reject `"2.5"`, `"2e0"`, number `2.50`, scale 1, and unit `"cm"`. Use stable field errors for type, decimal format, and unit mismatch. |
| Both, unsupported capability or invalid reference | Reject before rendering/submission evaluation. Preserve input draft data. Return `UNSUPPORTED_CAPABILITY` or `INVALID_FIELD_REFERENCE`, with the offending capability or rule/field ID. |

## Decisions requested from WSL

1. Agree the exact JSON schema, version and capability negotiation, strict input validation, UUID requirements, and ownership of the shared fixture directory and reviewed expected outputs.
2. Freeze nullability, whitespace, empty handling, unresolved conditions, hidden-answer dependencies, and evidence projection rules. Decide how to represent validation while an item is partially answered.
3. Confirm rule-node shapes and depth bounds, allowed operators, explicit repeat and document scope, and how validation treats references to hidden fields. Agree stable error codes, IDs, ordering and the distinction between diagnostic and submittable output.
4. Confirm decimal grammar including leading zeros, negative zero, boundary lengths and scale, unit identifiers, and whether cross-field decimal comparisons are in the first profile. Confirm the synthetic N/A explanation policy as a fixture rule.
5. Confirm server-issued repeat IDs and pinned submission order, exact receipt target fields, eligibility interpretation, handling of duplicated receipts, and whether dynamic membership is deferred. Freeze runner inputs so Kotlin, Python, and TypeScript can execute the same files without translation.

No evaluator or runner implementation is authorized by this proposal. Gate 1 signed v15 upgrade, background evidence retry, and Android end-to-end submission remain open. GPS work and production rollout remain on hold.
